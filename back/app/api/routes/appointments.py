from contextlib import contextmanager
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import AwareDatetime, BaseModel, ConfigDict, PositiveInt
from sqlalchemy.orm import Session

from app.api.catalog_dependencies import require_roles
from app.api.dependencies import get_database_session
from app.api.routes.extraction_centers import get_clock
from app.domain.entities.roles import UserRole
from app.domain.entities.user import AuthenticatedUser
from app.infrastructure.repositories.sqlalchemy_appointment_repository import SQLAlchemyAppointmentRepository
from app.infrastructure.repositories.sqlalchemy_extraction_center_repository import SQLAlchemyExtractionCenterRepository
from app.infrastructure.repositories.sqlalchemy_study_repository import SQLAlchemyStudyRepository
from app.use_cases.appointments import AppointmentConflict, AppointmentService, InvalidSlot, NotFound
from app.use_cases.studies import StudyService

router = APIRouter(prefix="/api", tags=["turnos de extracción"])
patient = require_roles(UserRole.PATIENT)
lab_administrator = require_roles(UserRole.LAB_ADMINISTRATOR)


def get_service(session: Session = Depends(get_database_session)):
    # Una sola sesión: el turno y el estado del estudio se confirman juntos.
    return AppointmentService(SQLAlchemyAppointmentRepository(session), SQLAlchemyExtractionCenterRepository(session),
                              StudyService(SQLAlchemyStudyRepository(session)))


@contextmanager
def http_errors():
    try:
        yield
    except NotFound as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except InvalidSlot as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    except AppointmentConflict as exc:
        raise HTTPException(409, detail=str(exc)) from exc


class AppointmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    study_id: PositiveInt
    center_id: PositiveInt
    starts_at: AwareDatetime


class AttendanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attended: bool


class CenterSummary(BaseModel):
    id: int
    name: str
    address: str
    city: str
    phone: str | None


class AppointmentResponse(BaseModel):
    id: int
    study_id: int
    starts_at: datetime
    status: str
    center: CenterSummary


class AttendanceResponse(BaseModel):
    id: int
    status: str
    patient_absences: int


@router.post("/appointments", response_model=AppointmentResponse, status_code=201)
def book_appointment(body: AppointmentRequest, actor: AuthenticatedUser = Depends(patient),
                     service: AppointmentService = Depends(get_service), now: datetime = Depends(get_clock)):
    with http_errors():
        return service.reservar(actor.id, body.study_id, body.center_id, body.starts_at, now)


@router.delete("/appointments/{appointment_id}", status_code=204)
def cancel_appointment(appointment_id: PositiveInt, actor: AuthenticatedUser = Depends(patient),
                       service: AppointmentService = Depends(get_service), now: datetime = Depends(get_clock)):
    with http_errors():
        service.cancelar(actor.id, appointment_id, now)
    return Response(status_code=204)


@router.get("/studies/{study_id}/appointment", response_model=AppointmentResponse)
def study_appointment(study_id: PositiveInt, actor: AuthenticatedUser = Depends(patient),
                      service: AppointmentService = Depends(get_service)):
    with http_errors():
        return service.turno_del_estudio(actor.id, study_id)


@router.patch("/appointments/{appointment_id}/attendance", response_model=AttendanceResponse)
def register_attendance(appointment_id: PositiveInt, body: AttendanceRequest,
                        _actor: AuthenticatedUser = Depends(lab_administrator),
                        service: AppointmentService = Depends(get_service)):
    with http_errors():
        return service.registrar_asistencia(appointment_id, body.attended)
