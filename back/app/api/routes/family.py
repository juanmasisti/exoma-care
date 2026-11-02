from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, PositiveInt
from sqlalchemy.orm import Session

from app.api.catalog_dependencies import require_roles
from app.api.dependencies import get_database_session
from app.domain.entities.family import FamilyMemberData
from app.domain.entities.roles import UserRole
from app.domain.entities.user import AuthenticatedUser
from app.domain.interfaces.family_repository import FamilyConflict
from app.infrastructure.repositories.sqlalchemy_family_repository import SQLAlchemyFamilyRepository
from app.infrastructure.repositories.sqlalchemy_patient_repository import SQLAlchemyPatientRepository
from app.infrastructure.repositories.sqlalchemy_pathology_repository import SQLAlchemyPathologyRepository
from app.use_cases.family import PatientFamilyService

router = APIRouter(prefix="/api/patients/{patient_id}/family", tags=["información familiar"])
physician = require_roles(UserRole.TREATING_PHYSICIAN)


def get_service(session: Session = Depends(get_database_session)):
    return PatientFamilyService(SQLAlchemyFamilyRepository(session), SQLAlchemyPatientRepository(session), SQLAlchemyPathologyRepository(session))


class FamilyMemberRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    full_name: str = Field(min_length=1, max_length=200)
    relationship: Literal["mother", "father", "sibling", "child", "aunt_uncle", "grandparent", "cousin", "other"]
    relationship_detail: str = Field(default="", max_length=100)
    symptom_ids: list[PositiveInt] = Field(default_factory=list, max_length=100)
    diagnosis_status: Literal["unknown", "none", "known"] = "unknown"
    diagnosis_ids: list[PositiveInt] = Field(default_factory=list, max_length=100)
    notes: str = Field(default="", max_length=4000)

    def to_domain(self):
        data = self.model_dump()
        data["symptom_ids"] = tuple(data["symptom_ids"])
        data["diagnosis_ids"] = tuple(data["diagnosis_ids"])
        return FamilyMemberData(**data)


class FamilyUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=0)
    members: list[FamilyMemberRequest] = Field(max_length=50)


class FamilyResponse(BaseModel):
    patient_id: int
    version: int
    members: list[dict]
    updated_at: datetime | None
    familiogram_status: Literal["not_configured"]


def translate_error(exc):
    code = 404 if isinstance(exc, LookupError) else 409 if isinstance(exc, FamilyConflict) else 422
    raise HTTPException(code, detail=str(exc)) from exc


@router.get("", response_model=FamilyResponse)
def get_family(patient_id: PositiveInt, _actor: AuthenticatedUser = Depends(physician), service: PatientFamilyService = Depends(get_service)):
    try:
        return service.get(patient_id)
    except LookupError as exc:
        translate_error(exc)


@router.get("/history")
def family_history(patient_id: PositiveInt, _actor: AuthenticatedUser = Depends(physician), service: PatientFamilyService = Depends(get_service)):
    try:
        return service.history(patient_id)
    except LookupError as exc:
        translate_error(exc)


@router.put("", response_model=FamilyResponse)
def save_family(patient_id: PositiveInt, body: FamilyUpdateRequest, actor: AuthenticatedUser = Depends(physician), service: PatientFamilyService = Depends(get_service)):
    try:
        return service.save(patient_id, body.version, [m.to_domain() for m in body.members], actor.id)
    except (ValueError, LookupError) as exc:
        translate_error(exc)
