import hmac
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.catalog_dependencies import require_roles
from app.api.dependencies import get_database_session
from app.api.routes.extraction_centers import get_clock
from app.config import get_settings
from app.domain.entities.roles import UserRole
from app.domain.entities.user import AuthenticatedUser
from app.infrastructure.logging_resample_notifier import LoggingResampleNotifier
from app.infrastructure.repositories.sqlalchemy_appointment_repository import SQLAlchemyAppointmentRepository
from app.infrastructure.repositories.sqlalchemy_sample_repository import SQLAlchemySampleRepository
from app.infrastructure.repositories.sqlalchemy_study_repository import SQLAlchemyStudyRepository
from app.use_cases.extraction import Conflict, ExtractionService, NotFound
from app.use_cases.studies import StudyService

router = APIRouter(prefix="/api", tags=["extracción"])
patient = require_roles(UserRole.PATIENT)


def get_resample_notifier():
    return LoggingResampleNotifier()


def get_service(session: Session = Depends(get_database_session), notifier=Depends(get_resample_notifier)):
    # Una sola sesión: aviso, muestra, turno y estado del estudio se confirman juntos.
    return ExtractionService(SQLAlchemySampleRepository(session), SQLAlchemyAppointmentRepository(session),
                             StudyService(SQLAlchemyStudyRepository(session)), notifier)


def require_webhook_secret(x_webhook_secret: Annotated[str | None, Header()] = None) -> None:
    """El bot no es un usuario: se autentica con un secreto compartido. Sin secreto configurado, nadie entra."""
    expected = get_settings().extraction_webhook_secret
    if (expected is None or x_webhook_secret is None
            or not hmac.compare_digest(x_webhook_secret.encode(), expected.get_secret_value().encode())):
        raise HTTPException(401, detail="Aviso de extracción no autorizado.")


@contextmanager
def http_errors():
    try:
        yield
    except NotFound as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except Conflict as exc:
        raise HTTPException(409, detail=str(exc)) from exc


class ExtractionNoticeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    external_id: Annotated[str, Field(min_length=1, max_length=100)]
    study_code: Annotated[str, Field(min_length=1, max_length=20)]
    # Finito, positivo y con 2 decimales: 1.999 no se redondea a 2.00 y pasa como válida.
    volume_ml: Annotated[Decimal, Field(gt=0, max_digits=5, decimal_places=2, allow_inf_nan=False)]
    taken_at: AwareDatetime


class ExtractionNoticeResponse(BaseModel):
    sample_id: int
    sample_status: str
    study_status: str


class SampleEventResponse(BaseModel):
    from_status: str | None
    to_status: str
    reason: str | None
    at: datetime


class SampleResponse(BaseModel):
    id: int
    volume_ml: Decimal
    status: str
    is_current: bool
    events: list[SampleEventResponse]


class TrackingResponse(BaseModel):
    study_id: int
    code: str
    status: str
    requires_new_extraction: bool
    samples: list[SampleResponse]


@router.post("/webhooks/extraction", status_code=201, response_model=ExtractionNoticeResponse,
             dependencies=[Depends(require_webhook_secret)])
def receive_extraction_notice(body: ExtractionNoticeRequest, response: Response,
                              service: ExtractionService = Depends(get_service), now: datetime = Depends(get_clock)):
    with http_errors():
        result, created = service.registrar_aviso(body.external_id, body.study_code, body.volume_ml,
                                                  body.taken_at, now)
    if not created:
        response.status_code = 200
    return result


@router.get("/studies/{study_id}/tracking", response_model=TrackingResponse)
def study_tracking(study_id: int, user: AuthenticatedUser = Depends(patient),
                   service: ExtractionService = Depends(get_service)):
    with http_errors():
        return service.seguimiento(user.id, study_id)
