from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from app.api.catalog_dependencies import get_catalog, require_roles
from app.domain.entities.roles import UserRole
from app.domain.interfaces.pathology_repository import DuplicatePathologyName
from app.use_cases.pathologies import PathologyCatalog

read_catalog = require_roles(UserRole.MEDICAL_MANAGER, UserRole.TREATING_PHYSICIAN)
write_catalog = require_roles(UserRole.MEDICAL_MANAGER)
router = APIRouter(prefix="/api", tags=["catálogo de patologías"])


class SymptomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    label: str
    code_system: str


class PathologyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    cardinal_symptom: SymptomResponse
    secondary_symptoms: list[SymptomResponse]


class PathologyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=160)
    cardinal_symptom_id: PositiveInt
    secondary_symptom_ids: list[PositiveInt] = Field(default_factory=list, max_length=100)


class ValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symptom_ids: list[PositiveInt] = Field(max_length=100)


class ValidationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    valid: bool
    criterion: str
    matched_cardinal: bool
    matched_secondary_ids: list[int]


def translate_error(exc: ValueError | LookupError):
    code = 404 if isinstance(exc, LookupError) else (
        409 if isinstance(exc, DuplicatePathologyName) else 422
    )
    raise HTTPException(status_code=code, detail=str(exc)) from exc


@router.get("/symptoms", response_model=list[SymptomResponse], dependencies=[Depends(read_catalog)])
def symptoms(q: str = Query(default="", max_length=100), catalog: PathologyCatalog = Depends(get_catalog)):
    return catalog.repository.list_symptoms(q)


@router.get("/pathologies", response_model=list[PathologyResponse], dependencies=[Depends(read_catalog)])
def pathologies(catalog: PathologyCatalog = Depends(get_catalog)):
    return catalog.repository.list_pathologies()


@router.get("/pathologies/{pathology_id}", response_model=PathologyResponse, dependencies=[Depends(read_catalog)])
def pathology(pathology_id: PositiveInt, catalog: PathologyCatalog = Depends(get_catalog)):
    try:
        return catalog.get(pathology_id)
    except LookupError as exc:
        translate_error(exc)


@router.post("/pathologies", response_model=PathologyResponse, status_code=201, dependencies=[Depends(write_catalog)])
def create_pathology(body: PathologyRequest, catalog: PathologyCatalog = Depends(get_catalog)):
    try:
        return catalog.save(body.name, body.cardinal_symptom_id, body.secondary_symptom_ids)
    except (ValueError, LookupError) as exc:
        translate_error(exc)


@router.put("/pathologies/{pathology_id}", response_model=PathologyResponse, dependencies=[Depends(write_catalog)])
def update_pathology(pathology_id: PositiveInt, body: PathologyRequest, catalog: PathologyCatalog = Depends(get_catalog)):
    try:
        return catalog.save(body.name, body.cardinal_symptom_id, body.secondary_symptom_ids, pathology_id)
    except (ValueError, LookupError) as exc:
        translate_error(exc)


@router.post("/pathologies/{pathology_id}/validate-suspicion", response_model=ValidationResponse,
             dependencies=[Depends(read_catalog)])
def validate(pathology_id: PositiveInt, body: ValidationRequest, catalog: PathologyCatalog = Depends(get_catalog)):
    try:
        return catalog.validate(pathology_id, body.symptom_ids)
    except (ValueError, LookupError) as exc:
        translate_error(exc)
