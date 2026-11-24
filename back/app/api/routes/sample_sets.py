from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_database_session
from app.api.logistics_dependencies import lab_administrator
from app.api.routes.shipments import get_sample_set_closed_handler
from app.domain.entities.logistics import TIMEZONE, SampleSetStatus, study_code
from app.domain.entities.user import AuthenticatedUser
from app.domain.interfaces.sample_set_hooks import SampleSetAssigner, SampleSetClosedHandler
from app.infrastructure.repositories.sqlalchemy_sample_repository import SQLAlchemySampleRepository
from app.infrastructure.repositories.sqlalchemy_sample_set_repository import SQLAlchemySampleSetRepository
from app.use_cases.sample_sets import SampleSetService

router = APIRouter(prefix="/api/sample-sets", tags=["sample sets"])


def get_service(session: Session = Depends(get_database_session),
                closed_handler: SampleSetClosedHandler = Depends(get_sample_set_closed_handler)) -> SampleSetService:
    return SampleSetService(SQLAlchemySampleSetRepository(session), SQLAlchemySampleRepository(session), closed_handler)


# Enganche que usa la llegada (T04) con Depends: corre en la sesión del pedido y no confirma nada.
def get_sample_set_assigner(service: SampleSetService = Depends(get_service)) -> SampleSetAssigner:
    return service


class SampleSetSummary(BaseModel):
    id: int
    status: SampleSetStatus
    is_urgent: bool
    created_at: datetime
    closed_at: datetime | None


class SampleSetListItem(SampleSetSummary):
    sample_count: int


class SampleSetSample(BaseModel):
    slot: int
    sample_id: int
    study_code: str


class SampleSetDetail(SampleSetSummary):
    # Solo el código del estudio: el administrativo no necesita los datos del paciente para armar el envío.
    samples: list[SampleSetSample]


def _local_dates(sample_set: dict) -> dict:
    # En hora de Argentina, como el resto de logística: el front muestra la fecha tal cual llega.
    return {**sample_set, "created_at": sample_set["created_at"].astimezone(TIMEZONE),
            "closed_at": sample_set["closed_at"] and sample_set["closed_at"].astimezone(TIMEZONE)}


@router.get("", response_model=list[SampleSetListItem])
def list_sample_sets(status: SampleSetStatus | None = None, _actor: AuthenticatedUser = Depends(lab_administrator),
                     service: SampleSetService = Depends(get_service)):
    return [_local_dates(sample_set) for sample_set in service.list_sample_sets(status and status.value)]


@router.get("/{sample_set_id}", response_model=SampleSetDetail)
def sample_set_detail(sample_set_id: int, _actor: AuthenticatedUser = Depends(lab_administrator),
                      service: SampleSetService = Depends(get_service)):
    try:
        sample_set = service.sample_set(sample_set_id)
    except LookupError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    samples = [{"slot": item["slot"], "sample_id": item["sample_id"], "study_code": study_code(item["study_id"])}
               for item in sample_set["items"]]
    return {**_local_dates(sample_set), "samples": samples}
