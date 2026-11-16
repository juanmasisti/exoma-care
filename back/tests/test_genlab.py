import asyncio
import json
import httpx
import pytest

from app.infrastructure.genlab_chatbot import GenLabChatbot
from app.domain.interfaces.chatbot_provider import ChatbotFailure, ChatbotUnavailable, ChatbotRateLimited


def provider(handler):
    return GenLabChatbot('https://example.test/chat', 'test-api', 'test-token', transport=httpx.MockTransport(handler))


@pytest.mark.parametrize('kind', ['respuesta', 'fuera_de_alcance', 'derivar_medico', 'sin_informacion'])
def test_post_contract(kind):
    def handler(request):
        assert request.headers['apikey'] == 'test-api'
        assert request.headers['x-chatbot-token'] == 'test-token'
        assert 'authorization' not in request.headers
        assert json.loads(request.content) == {'mensaje': 'Pregunta', 'conversacion_id': 'previous'}
        return httpx.Response(200, json={'respuesta': ' Texto exacto\n', 'conversacion_id': 'next', 'tipo': kind})
    result = asyncio.run(provider(handler).answer('Pregunta', 'previous'))
    assert result.answer == ' Texto exacto\n'
    assert result.conversation_id == 'next' and result.kind == kind


@pytest.mark.parametrize('status', [401, 405, 422, 500, 302])
def test_errors_sanitized(status):
    with pytest.raises(ChatbotFailure):
        asyncio.run(provider(lambda _: httpx.Response(status, json={'detail': 'private'})).answer('Hola', None))


def test_rate_limit_does_not_retry_in_backend():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={'Retry-After': '12'})
    with pytest.raises(ChatbotRateLimited) as failure:
        asyncio.run(provider(handler).answer('Hola', None))
    assert failure.value.retry_after == 12 and len(calls) == 1


def test_unavailable_preserves_public_detail():
    with pytest.raises(ChatbotUnavailable) as failure:
        asyncio.run(provider(lambda _: httpx.Response(503, json={'detail': 'Servicio apagado temporalmente'})).answer('Hola', None))
    assert str(failure.value) == 'Servicio apagado temporalmente'


@pytest.mark.parametrize('body', [{}, {'respuesta':'', 'conversacion_id':'id','tipo':'respuesta'}, {'respuesta':'ok','conversacion_id':'id','tipo':'unknown'}])
def test_invalid_success(body):
    with pytest.raises(ChatbotFailure):
        asyncio.run(provider(lambda _: httpx.Response(200, json=body)).answer('Hola', None))


def test_health_without_credentials():
    def handler(request):
        assert request.method == 'GET'
        assert 'apikey' not in request.headers and 'x-chatbot-token' not in request.headers
        return httpx.Response(200, json={'estado': 'ok'})
    assert asyncio.run(provider(handler).health()) is True


def test_compressed_response_decoded_once():
    import gzip
    content = gzip.compress(b'{"estado":"ok"}')
    assert asyncio.run(provider(lambda _: httpx.Response(200, content=content, headers={'Content-Encoding':'gzip'})).health()) is True
