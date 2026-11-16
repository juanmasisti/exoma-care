import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.catalog_dependencies import get_current_user
from app.domain.entities.user import AuthenticatedUser
from app.domain.entities.roles import UserRole


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('CHATBOT_URL', '')
    monkeypatch.setenv('JWT_SECRET_KEY', 'chatbot-test-secret-with-at-least-32-bytes')
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(1, 'patient@example.test', UserRole.PATIENT)
    try:
        with TestClient(app) as http:
            yield http
    finally:
        app.dependency_overrides.clear()


def test_not_configured_is_explicit(client):
    response = client.get('/api/chatbot/status')
    assert response.status_code == 200
    assert response.json() == {'available': False, 'message': None}
    response = client.post('/api/chatbot/messages', json={'question': '¿Qué es Fabry?'})
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'chatbot_unavailable'


@pytest.mark.parametrize('role', [UserRole.TREATING_PHYSICIAN, UserRole.MEDICAL_MANAGER])
def test_other_roles_cannot_query(client, role):
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(2, 'other@example.test', role)
    assert client.get('/api/chatbot/status').status_code == 403
    assert client.post('/api/chatbot/messages', json={'question': 'Hola'}).status_code == 403


def test_anonymous_cannot_query(client):
    app.dependency_overrides.pop(get_current_user)
    assert client.get('/api/chatbot/status').status_code == 401
    assert client.post('/api/chatbot/messages', json={'question': 'Hola'}).status_code == 401


@pytest.mark.parametrize('body', [{'question': ''}, {'question': '   '}, {'question': 'a' * 1001}, {'question': 5}, {'question': 'Hola', 'patient_id': 2}])
def test_invalid_questions(client, body):
    assert client.post('/api/chatbot/messages', json=body).status_code == 422


def provider_override(provider):
    from app.api.routes.chatbot import get_chatbot_service
    from app.use_cases.chatbot import ChatbotService
    app.dependency_overrides[get_chatbot_service] = lambda: ChatbotService(provider)


def test_only_question_is_forwarded_and_answer_is_returned(client):
    class Provider:
        available = True
        async def health(self):
            return True
        async def answer(self, question, conversation_id):
            assert question == '¿Qué es Fabry?'
            from app.domain.interfaces.chatbot_provider import ChatbotReply
            return ChatbotReply('Respuesta de prueba', 'upstream-id', 'respuesta')
    provider_override(Provider())
    assert client.get('/api/chatbot/status').json() == {'available': True, 'message': None}
    response = client.post('/api/chatbot/messages', json={'question': '  ¿Qué es Fabry?  '})
    assert response.status_code == 200
    assert response.json()['answer'] == 'Respuesta de prueba'
    assert response.json()['conversation_token']
    assert response.json()['kind'] == 'respuesta'
    assert response.headers['cache-control'] == 'no-store'


@pytest.mark.parametrize('result', ['', '   ', None, {'answer': 'wrong'}, 'a' * 16001])
def test_invalid_provider_answers_are_rejected(client, result):
    class Provider:
        available = True
        async def health(self):
            return True
        async def answer(self, question, conversation_id):
            return result
    provider_override(Provider())
    assert client.post('/api/chatbot/messages', json={'question': 'Hola'}).status_code == 502


@pytest.mark.parametrize('error,status', [(TimeoutError('secret'), 504), (RuntimeError('secret'), 502)])
def test_provider_errors_do_not_leak_details(client, error, status):
    class Provider:
        available = True
        async def health(self):
            return True
        async def answer(self, question, conversation_id):
            raise error
    provider_override(Provider())
    response = client.post('/api/chatbot/messages', json={'question': 'Hola'})
    assert response.status_code == status
    assert 'secret' not in response.text


def test_deadline_cancels_a_slow_provider(monkeypatch):
    import asyncio
    import app.use_cases.chatbot as module
    wait_for = asyncio.wait_for
    cancelled = []

    async def short_deadline(awaitable, timeout):
        assert timeout == 20
        return await wait_for(awaitable, timeout=0.01)

    class SlowProvider:
        available = True
        async def health(self):
            return True
        async def answer(self, question, conversation_id):
            try:
                await asyncio.sleep(60)
            finally:
                cancelled.append(True)

    monkeypatch.setattr(module.asyncio, 'wait_for', short_deadline)
    with pytest.raises(TimeoutError):
        asyncio.run(module.ChatbotService(SlowProvider()).ask('Hola'))
    assert cancelled == [True]


def test_conversation_bound_to_patient(client):
    from app.domain.interfaces.chatbot_provider import ChatbotReply
    calls = []
    class Provider:
        available = True
        async def answer(self, question, conversation_id):
            calls.append(conversation_id)
            return ChatbotReply('Respuesta', 'upstream-id', 'respuesta')
    provider_override(Provider())
    first = client.post('/api/chatbot/messages', json={'question': 'Hola'}).json()
    token = first['conversation_token']
    assert client.post('/api/chatbot/messages', json={'question': '¿Y después?', 'conversation_token': token}).status_code == 200
    assert calls == [None, 'upstream-id']
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(2, 'other@example.test', UserRole.PATIENT)
    assert client.post('/api/chatbot/messages', json={'question': 'Hola', 'conversation_token': token}).status_code == 400
    assert len(calls) == 2
    assert client.post('/api/chatbot/messages', json={'question': 'Hola', 'conversation_token': 'upstream-id'}).status_code == 400


def test_expired_conversation(client):
    import jwt
    from app.config import get_jwt_secret
    token = jwt.encode({'sub':'1', 'cid':'id', 'iat':1, 'exp':2, 'aud':'exoma-chatbot', 'iss':'exoma-care'}, get_jwt_secret(), algorithm='HS256')
    assert client.post('/api/chatbot/messages', json={'question':'Hola', 'conversation_token':token}).status_code == 400


def test_rate_limit_header(client):
    from app.domain.interfaces.chatbot_provider import ChatbotRateLimited
    class Provider:
        available = True
        async def answer(self, question, conversation_id):
            raise ChatbotRateLimited(17)
    provider_override(Provider())
    response = client.post('/api/chatbot/messages', json={'question':'Hola'})
    assert response.status_code == 429 and response.headers['retry-after'] == '17'
