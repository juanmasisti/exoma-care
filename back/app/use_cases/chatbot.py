import asyncio

from app.domain.interfaces.chatbot_provider import ChatbotFailure, ChatbotProvider, ChatbotUnavailable, ChatbotRateLimited, ChatbotReply


class ChatbotService:
    def __init__(self, provider: ChatbotProvider):
        self.provider = provider

    @property
    def available(self) -> bool:
        # Configuration readiness, not a remote health check.
        return self.provider.available

    async def health(self) -> bool:
        if not self.available:
            return False
        return await asyncio.wait_for(self.provider.health(), timeout=20)

    async def ask(self, question: str, conversation_id: str | None = None) -> ChatbotReply:
        if not self.available:
            raise ChatbotUnavailable()
        try:
            answer = await asyncio.wait_for(self.provider.answer(question, conversation_id), timeout=20)
        except (TimeoutError, ChatbotUnavailable, ChatbotRateLimited):
            raise
        except Exception:
            # Never propagate provider payloads, credentials or URLs to the API.
            raise ChatbotFailure() from None
        if not isinstance(answer, ChatbotReply) or not isinstance(answer.answer, str) or not answer.answer.strip() or len(answer.answer) > 16000:
            raise ChatbotFailure()
        return answer
