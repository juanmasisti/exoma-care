"""GenLab wire contract. Credentials and HTTP details stay in the backend."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx

from app.domain.interfaces.chatbot_provider import ChatbotFailure, ChatbotRateLimited, ChatbotReply, ChatbotUnavailable

KINDS = {'respuesta', 'fuera_de_alcance', 'derivar_medico', 'sin_informacion'}


def retry_seconds(value: str | None) -> int:
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        try:
            seconds = int((parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()) + 1
        except (TypeError, ValueError, OverflowError):
            seconds = 5
    return max(1, min(seconds, 86400))


class GenLabChatbot:
    def __init__(self, url, apikey, token, *, transport=None):
        self.url, self.apikey, self.token = url, apikey, token
        self.transport = transport
        self.available = bool(url and apikey and token)

    async def request(self, method, **kwargs):
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=False, transport=self.transport) as client:
                # Bound response memory; the service is text-only, not a file endpoint.
                async with client.stream(method, self.url, **kwargs) as response:
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > 131072:
                            raise ChatbotFailure()
                    # aiter_bytes already decompresses; don't decode gzip a second time.
                    headers = {key: value for key, value in response.headers.items()
                               if key not in {'content-encoding', 'content-length', 'transfer-encoding'}}
                    return httpx.Response(response.status_code, headers=headers, content=bytes(content))
        except httpx.TimeoutException:
            raise TimeoutError() from None
        except httpx.HTTPError:
            raise ChatbotFailure() from None

    async def health(self) -> bool:
        response = await self.request('GET')
        if response.status_code == 503:
            self.unavailable(response)
        try:
            return response.status_code == 200 and response.json().get('estado') == 'ok'
        except (ValueError, AttributeError):
            return False

    def unavailable(self, response):
        try:
            detail = response.json().get('detail')
        except (ValueError, AttributeError):
            detail = None
        message = detail if isinstance(detail, str) and detail.strip() and len(detail) <= 4000 else 'El servicio de consultas no está disponible en este momento.'
        # Defensive redaction even if the provider accidentally echoes a header.
        for secret in (self.apikey, self.token):
            if secret:
                message = message.replace(secret, '[credencial]')
        raise ChatbotUnavailable(message)

    async def answer(self, question: str, conversation_id: str | None) -> ChatbotReply:
        response = await self.request('POST', headers={'apikey': self.apikey, 'x-chatbot-token': self.token},
                                      json={'mensaje': question, 'conversacion_id': conversation_id})
        if response.status_code == 429:
            raise ChatbotRateLimited(retry_seconds(response.headers.get('retry-after')))
        if response.status_code == 503:
            self.unavailable(response)
        if response.status_code != 200:
            # In particular, upstream 401 must not log out an Exoma Care user.
            raise ChatbotFailure()
        try:
            data = response.json()
            answer, cid, kind = data['respuesta'], data['conversacion_id'], data['tipo']
            if (not isinstance(answer, str) or not answer.strip() or len(answer) > 16000
                    or not isinstance(cid, str) or not cid.strip() or len(cid) > 200
                    or not isinstance(kind, str) or kind not in KINDS):
                raise ChatbotFailure()
            return ChatbotReply(answer, cid, kind)
        except (ValueError, KeyError, TypeError):
            raise ChatbotFailure() from None
