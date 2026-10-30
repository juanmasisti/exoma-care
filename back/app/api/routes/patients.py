from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, PositiveInt
from sqlalchemy.orm import Session

from app.api.catalog_dependencies import require_roles
from app.api.dependencies import get_database_session
from app.domain.entities.clinical_patient import PatientData
from app.domain.entities.roles import UserRole
from app.domain.entities.user import AuthenticatedUser
from app.domain.interfaces.patient_repository import PatientConflict
from app.infrastructure.repositories.sqlalchemy_patient_repository import SQLAlchemyPatientRepository
from app.infrastructure.repositories.sqlalchemy_pathology_repository import SQLAlchemyPathologyRepository
from app.use_cases.patients import ClinicalValidationError, PatientClinicalService

router = APIRouter(prefix="/api/patients", tags=["pacientes e información clínica"])
physician = require_roles(UserRole.TREATING_PHYSICIAN)


def get_service(session: Session = Depends(get_database_session)):
    return PatientClinicalService(SQLAlchemyPatientRepository(session), SQLAlchemyPathologyRepository(session))


class PatientRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    dni: str = Field(min_length=1, max_length=30)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    birth_date: date
    phone: str = Field(min_length=1, max_length=30)
    email: str = Field(min_length=1, max_length=255)
    clinical_summary: str = Field(min_length=1, max_length=20000)
    suspicion_type: Literal["clinical", "family"]
    family_history: str = Field(default="", max_length=10000)
    pathology_ids: list[PositiveInt] = Field(min_length=1, max_length=100)
    symptom_ids: list[PositiveInt] = Field(default_factory=list, max_length=100)

    def to_domain(self):
        data = self.model_dump(exclude={"version"})
        data["pathology_ids"] = tuple(data["pathology_ids"])
        data["symptom_ids"] = tuple(data["symptom_ids"])
        return PatientData(**data)


class PatientUpdateRequest(PatientRequest):
    version: PositiveInt


class PatientSummary(BaseModel):
    id: int
    dni: str
    first_name: str
    last_name: str
    birth_date: date | None
    suspicion_type: str | None
    pathology_names: list[str]
    version: int
    access_status: Literal["pending", "linked"]
    updated_at: datetime | None
    clinical_record_complete: bool


class PatientListResponse(BaseModel):
    items: list[PatientSummary]
    total: int
    limit: int
    offset: int


class PatientResponse(BaseModel):
    id: int
    dni: str
    first_name: str
    last_name: str
    birth_date: date | None
    phone: str
    email: str
    clinical_summary: str
    suspicion_type: str | None
    family_history: str
    pathology_ids: list[int]
    symptom_ids: list[int]
    suspicions: list[dict]
    symptoms: list[dict]
    version: int
    created_by_physician_id: int | None
    access_status: Literal["pending", "linked"]
    created_at: datetime | None
    updated_at: datetime | None
    clinical_record_complete: bool


class EvaluationResponse(BaseModel):
    valid: bool
    results: list[dict]


def clinical_error(exc):
    if isinstance(exc, ClinicalValidationError):
        raise HTTPException(422, detail={"message": str(exc), "results": exc.results}) from exc
    code = 404 if isinstance(exc, LookupError) else 409 if isinstance(exc, PatientConflict) else 422
    raise HTTPException(code, detail=str(exc)) from exc


@router.get("", response_model=PatientListResponse)
def list_patients(q: str = Query(default="", max_length=100), limit: int = Query(default=20, ge=1, le=100),
                  offset: int = Query(default=0, ge=0), _actor: AuthenticatedUser = Depends(physician),
                  service: PatientClinicalService = Depends(get_service)):
    # Decisión confirmada: médicos tratantes pueden consultar todos los pacientes.
    return service.patients.list(None, q, limit, offset)


@router.post("/validate", response_model=EvaluationResponse)
def evaluate_patient(body: PatientRequest, _actor: AuthenticatedUser = Depends(physician),
                     service: PatientClinicalService = Depends(get_service)):
    try:
        _, evaluation = service.evaluate(body.to_domain())
        return evaluation
    except ValueError as exc:
        clinical_error(exc)


@router.post("", response_model=PatientResponse, status_code=201)
def create_patient(body: PatientRequest, actor: AuthenticatedUser = Depends(physician),
                   service: PatientClinicalService = Depends(get_service)):
    try:
        return service.save(body.to_domain(), actor.id, None)
    except (ValueError, LookupError) as exc:
        clinical_error(exc)


@router.get("/{patient_id}", response_model=PatientResponse)
def get_patient(patient_id: PositiveInt, _actor: AuthenticatedUser = Depends(physician),
                service: PatientClinicalService = Depends(get_service)):
    try:
        return service.get(patient_id, None)
    except LookupError as exc:
        clinical_error(exc)


@router.put("/{patient_id}", response_model=PatientResponse)
def update_patient(patient_id: PositiveInt, body: PatientUpdateRequest, actor: AuthenticatedUser = Depends(physician),
                   service: PatientClinicalService = Depends(get_service)):
    try:
        return service.save(body.to_domain(), actor.id, None, patient_id, body.version)
    except (ValueError, LookupError) as exc:
        clinical_error(exc)


@router.get("/{patient_id}/history")
def patient_history(patient_id: PositiveInt, _actor: AuthenticatedUser = Depends(physician),
                    service: PatientClinicalService = Depends(get_service)):
    try:
        service.get(patient_id, None)
        return service.patients.history(patient_id)
    except LookupError as exc:
        clinical_error(exc)
