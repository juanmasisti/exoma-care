from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, PositiveInt
from sqlalchemy.orm import Session

from app.api.catalog_dependencies import require_roles
from app.api.dependencies import get_database_session
from app.api.dependencies import get_enviar_notificacion_use_case
from app.config import (
    get_apigen_api_key,
    get_apigen_base_url,
)
from app.domain.entities.roles import UserRole
from app.domain.entities.study import StudyStatus
from app.domain.entities.user import AuthenticatedUser
from app.infrastructure.external_services.apigen_client import ApigenClient
from app.infrastructure.external_services.errors import ExternalServiceError
from app.infrastructure.repositories.sqlalchemy_study_repository import (
    SQLAlchemyStudyRepository,
)
from app.use_cases.analisis_bioinformatico import (
    MissingPatientEmailError,
    ProcesarAnalisisUseCase,
    StudyNotFoundError,
    StudyStateConflictError,
)
from app.use_cases.notifications import EnviarNotificacionUseCase

router = APIRouter(prefix="/api/estudios", tags=["análisis bioinformático"])
bioinformatician = require_roles(UserRole.BIOINFORMATICIAN)


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    codigo_patologia: str = Field(min_length=1, max_length=100)
    variantes: list[dict[str, Any]] = Field(min_length=1, max_length=1000)


class AnalysisResponse(BaseModel):
    study_id: int
    status: str
    result: dict[str, Any]


def get_analysis_use_case(
    session: Session = Depends(get_database_session),
    notifications: EnviarNotificacionUseCase = Depends(
        get_enviar_notificacion_use_case
    ),
) -> ProcesarAnalisisUseCase:
    return ProcesarAnalisisUseCase(
        SQLAlchemyStudyRepository(session),
        ApigenClient(
            get_apigen_api_key(),
            base_url=get_apigen_base_url(),
        ),
        notifications,
    )


@router.post("/{study_id}/analizar", response_model=AnalysisResponse)
async def analyze_study(
    study_id: PositiveInt,
    body: AnalysisRequest,
    actor: AuthenticatedUser = Depends(bioinformatician),
    use_case: ProcesarAnalisisUseCase = Depends(get_analysis_use_case),
) -> AnalysisResponse:
    try:
        result = await use_case.execute(
            study_id=study_id,
            analyst_id=actor.id,
            codigo_patologia=body.codigo_patologia,
            variantes=body.variantes,
        )
    except StudyNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StudyStateConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except MissingPatientEmailError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ExternalServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return AnalysisResponse(
        study_id=study_id,
        status=StudyStatus.RESULT_AVAILABLE.value,
        result=result,
    )
