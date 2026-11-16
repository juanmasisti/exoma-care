from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, StringConstraints

from app.api.catalog_dependencies import require_roles
from app.api.catalog_dependencies import get_current_user
from app.config import get_settings
from app.domain.entities.user import AuthenticatedUser
from app.infrastructure.genlab_chatbot import GenLabChatbot
from app.infrastructure.chatbot_conversation import encode_conversation, decode_conversation
from app.domain.entities.roles import UserRole
from app.domain.interfaces.chatbot_provider import ChatbotFailure, ChatbotUnavailable, ChatbotRateLimited
from app.infrastructure.unconfigured_chatbot import UnconfiguredChatbot
from app.use_cases.chatbot import ChatbotService

router = APIRouter(prefix='/api/chatbot', tags=['consultas del paciente'],
                   dependencies=[Depends(require_roles(UserRole.PATIENT))])


def get_chatbot_service() -> ChatbotService:
    settings = get_settings()
    if settings.chatbot_url and settings.chatbot_apikey.get_secret_value() and settings.chatbot_token.get_secret_value():
        return ChatbotService(GenLabChatbot(settings.chatbot_url, settings.chatbot_apikey.get_secret_value(), settings.chatbot_token.get_secret_value()))
    return ChatbotService(UnconfiguredChatbot())


class Question(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=1000)]
    conversation_token: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=2048)] | None = None


class Answer(BaseModel):
    answer: str
    conversation_token: str
    kind: str


class Availability(BaseModel):
    available: bool
    message: str | None = None


@router.get('/status', response_model=Availability)
async def status(response: Response, service: ChatbotService = Depends(get_chatbot_service)):
    response.headers['Cache-Control'] = 'no-store'
    try:
        return Availability(available=await service.health())
    except ChatbotUnavailable as exc:
        return Availability(available=False, message=str(exc) or None)
    except (ChatbotFailure, TimeoutError):
        raise HTTPException(503, detail='No se pudo comprobar el servicio de consultas.', headers={'Cache-Control': 'no-store'}) from None


@router.post('/messages', response_model=Answer, responses={
    401: {'description': 'Sesión ausente o inválida'},
    403: {'description': 'Solo pacientes'},
    400: {'description': 'Conversación vencida o inválida'},
    429: {'description': 'Límite del grupo; esperar Retry-After y reintentar una vez'},
    503: {'description': 'Integración aún no disponible'},
    502: {'description': 'Fallo o respuesta inválida del proveedor'},
    504: {'description': 'El proveedor no respondió a tiempo'},
})
async def ask(body: Question, response: Response, service: ChatbotService = Depends(get_chatbot_service), actor: AuthenticatedUser = Depends(get_current_user)):
    try:
        cid = decode_conversation(body.conversation_token, actor.id)
    except ValueError as exc:
        raise HTTPException(400, detail={'code': 'conversation_invalid', 'message': str(exc)}, headers={'Cache-Control': 'no-store'}) from None
    try:
        answer = await service.ask(body.question, cid)
    except ChatbotRateLimited as exc:
        raise HTTPException(429, detail={'code': 'chatbot_rate_limited', 'message': 'Se alcanzó el límite de consultas. Esperá antes de volver a intentar.'}, headers={'Retry-After': str(exc.retry_after), 'Cache-Control': 'no-store'}) from None
    except ChatbotUnavailable as exc:
        raise HTTPException(503, detail={'code': 'chatbot_unavailable', 'message': str(exc) or 'El servicio de consultas aún no está disponible.'}, headers={'Cache-Control': 'no-store'}) from None
    except TimeoutError:
        raise HTTPException(504, detail={'code': 'chatbot_timeout', 'message': 'La respuesta tardó demasiado. Podés volver a intentar.'}, headers={'Cache-Control': 'no-store'}) from None
    except ChatbotFailure:
        raise HTTPException(502, detail={'code': 'chatbot_failure', 'message': 'No se pudo obtener una respuesta. Intentá nuevamente más tarde.'}, headers={'Cache-Control': 'no-store'}) from None
    response.headers['Cache-Control'] = 'no-store'
    return Answer(answer=answer.answer, conversation_token=encode_conversation(answer.conversation_id, actor.id), kind=answer.kind)
