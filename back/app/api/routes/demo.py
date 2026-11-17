"""SIMULACIÓN para demo y pruebas (T03d). Apagado por defecto con DEMO_TOOLS_ENABLED."""
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from app.api.catalog_dependencies import require_roles
from app.api.routes.extraction import (
    ExtractionNoticeResponse, StudyCode, VolumeMl, get_service, http_errors,
)
from app.api.routes.extraction_centers import get_clock
from app.config import get_settings
from app.domain.entities.roles import UserRole
from app.use_cases.extraction import ExtractionService


def require_demo_tools() -> None:
    # Apagado, responde como una ruta que no existe, antes de pedir sesión.
    if not get_settings().demo_tools_enabled:
        raise HTTPException(404, detail="Not Found")


router = APIRouter(prefix="/api/demo", tags=["demo"], dependencies=[Depends(require_demo_tools)])
lab_administrator = require_roles(UserRole.LAB_ADMINISTRATOR)


class SimulatedNoticeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    study_code: StudyCode
    volume_ml: VolumeMl


class WaitingStudyResponse(BaseModel):
    study_id: int
    code: str
    patient_name: str
    center_name: str
    starts_at: datetime


@router.get("/extraction-notice/studies", response_model=list[WaitingStudyResponse],
            dependencies=[Depends(lab_administrator)])
def waiting_studies(service: ExtractionService = Depends(get_service)):
    return service.estudios_esperando_aviso()


@router.post("/extraction-notice", status_code=201, response_model=ExtractionNoticeResponse,
             dependencies=[Depends(lab_administrator)])
def simulate_extraction_notice(body: SimulatedNoticeRequest, service: ExtractionService = Depends(get_service),
                               now: datetime = Depends(get_clock)):
    """El mismo caso de uso que el webhook, con un aviso nuevo cada vez y la hora actual."""
    with http_errors():
        result, _ = service.registrar_aviso(f"sim-{uuid4()}", body.study_code, body.volume_ml, now, now)
    return result
