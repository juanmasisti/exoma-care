from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, PositiveInt
from app.api.catalog_dependencies import get_catalog, require_roles
from app.api.dependencies import get_apigen_client as shared_apigen_client, get_cdss_client as shared_cdss_client
from app.api.routes.pathologies import PathologyResponse
from app.config import get_settings
from app.domain.entities.roles import UserRole
from app.infrastructure.external_services.errors import ExternalServiceError
from app.use_cases.clinical_integrations import ClinicalIntegrations

def get_apigen_client():
    try:
        return shared_apigen_client()
    except (RuntimeError, ValueError):
        raise HTTPException(503, "La integración Apigen no está configurada.") from None

def get_cdss_client():
    try:
        return shared_cdss_client()
    except (RuntimeError, ValueError):
        raise HTTPException(503, "La integración CDSS no está configurada.") from None


router = APIRouter(prefix="/api/clinical-integrations", tags=["integraciones clínicas"])
read = require_roles(UserRole.MEDICAL_MANAGER, UserRole.TREATING_PHYSICIAN)
write = require_roles(UserRole.MEDICAL_MANAGER)

class LinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    apigen_code: str = Field(min_length=1, max_length=100)
    de_grupo: bool = False
    cdss_code: str | None = Field(default=None, min_length=1, max_length=100)

class GeneticRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    codigo: str = Field(pattern=r"^[A-Z0-9_-]{1,100}$")
    nombre: str = Field(min_length=1, max_length=160)
    genes: list[Annotated[str, Field(pattern=r"^[A-Za-z0-9.-]{1,50}$")]] = Field(min_length=1, max_length=100)
    herencia: Literal["autosomica_recesiva", "autosomica_dominante", "ligada_al_x"]
    confirm_remote_write: Literal[True]

class AdviceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symptom_ids: list[PositiveInt] = Field(min_length=1, max_length=100)

def error(exc):
    if isinstance(exc, ExternalServiceError):
        raise HTTPException(exc.status_code, str(exc)) from None
    raise HTTPException(404 if isinstance(exc, LookupError) else 422, str(exc)) from None

@router.get("/apigen/pathologies", dependencies=[Depends(read)])
async def genetic_catalog(apigen=Depends(get_apigen_client)):
    try:
        return await apigen.listar_patologias_grupo(get_settings().apigen_group_id)
    except ExternalServiceError as exc:
        error(exc)

@router.get("/cdss/pathologies", dependencies=[Depends(read)])
async def clinical_catalog(cdss=Depends(get_cdss_client)):
    try:
        return await cdss.obtener_catalogo_completo()
    except ExternalServiceError as exc:
        error(exc)

@router.get("/apigen/genes", dependencies=[Depends(write)])
async def genes(q: str = Query(min_length=2, max_length=50, pattern=r"^[A-Za-z0-9.-]+$"), apigen=Depends(get_apigen_client)):
    try:
        return await apigen.buscar_genes_clinicos(q)
    except ExternalServiceError as exc:
        error(exc)

@router.post("/apigen/pathologies", dependencies=[Depends(write)], status_code=201)
async def create_genetic_pathology(body: GeneticRequest, apigen=Depends(get_apigen_client)):
    # This action writes only to Apigen. Linking local criteria is a separate recoverable step.
    try:
        existing = await apigen.listar_patologias_grupo(get_settings().apigen_group_id)
        if any(item["codigo"] == body.codigo for item in existing):
            raise HTTPException(409, "Ese código ya existe. Actualizá el catálogo y asociá la identidad existente; no se sobrescribió.")
        result = await apigen.alta_patologia(get_settings().apigen_group_id, body.codigo, body.nombre, list(dict.fromkeys(body.genes)), body.herencia)
        return {"pathology": result, "message": "Alta externa realizada. Asociá esta identidad a una patología local para configurar sus criterios."}
    except ExternalServiceError:
        raise HTTPException(502, "No se pudo confirmar el alta externa. Actualizá el catálogo de Apigen antes de reintentar; puede haberse completado allí.") from None

@router.put("/pathologies/{pathology_id}/identity", response_model=PathologyResponse, dependencies=[Depends(write)])
async def link_identity(pathology_id: PositiveInt, body: LinkRequest, catalog=Depends(get_catalog), apigen=Depends(get_apigen_client), cdss=Depends(get_cdss_client)):
    try:
        return await ClinicalIntegrations(catalog, apigen, cdss).link(pathology_id, body.apigen_code, body.de_grupo, body.cdss_code)
    except (ExternalServiceError, LookupError, ValueError) as exc:
        error(exc)

@router.post("/cdss/advice", dependencies=[Depends(read)])
async def advice(body: AdviceRequest, catalog=Depends(get_catalog), cdss=Depends(get_cdss_client)):
    try:
        return await ClinicalIntegrations(catalog, cdss=cdss).advise(body.symptom_ids)
    except (ExternalServiceError, LookupError, ValueError) as exc:
        error(exc)


@router.post("/cdss/pathologies/{code}/draft", dependencies=[Depends(write)])
async def import_cdss_draft(code: str, catalog=Depends(get_catalog), cdss=Depends(get_cdss_client)):
    # Import trusted concepts only; local pathology criteria change only on explicit save.
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError
    from app.infrastructure.database.catalog_models import SymptomModel
    try:
        entries = await cdss.obtener_catalogo_completo()
        selected = next((p for p in entries if p["codigo"] == code), None)
        if selected is None:
            raise LookupError("La patología no existe en CDSS.")
        session = catalog.repository.session
        result = {"codigo": code, "nombre": selected["nombre"], "cardinals": [], "secondary": []}
        for symptom in selected["sintomas"]:
            query = select(SymptomModel).where(SymptomModel.code_system == "SNOMED", SymptomModel.code == symptom["snomed_codigo"])
            term = session.scalar(query)
            if term is None:
                term = SymptomModel(code_system="SNOMED", code=symptom["snomed_codigo"], label=symptom["termino"])
                session.add(term)
                try:
                    session.commit()
                except IntegrityError:
                    session.rollback()
                    term = session.scalar(query)
                    if term is None:
                        raise
            result["cardinals" if symptom["es_cardinal"] else "secondary"].append({"id": term.id, "code": term.code, "label": term.label, "code_system": term.code_system})
        return result
    except (ExternalServiceError, LookupError, ValueError) as exc:
        error(exc)
