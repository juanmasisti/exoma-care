"""Solicitud de estudio, presupuesto, modalidad de pago, cobertura, pago (EC-10 a EC-13) y
reanálisis (EC-14)."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from app.api.catalog_dependencies import require_roles
from app.api.study_dependencies import get_study_payment_service, get_study_request_service
from app.api.study_http import HANDLED_ERRORS, to_http_error
from app.domain.entities.roles import UserRole
from app.domain.entities.user import AuthenticatedUser
from app.use_cases.study_payments import MAX_DEMAND_BYTES, StudyPaymentService
from app.use_cases.study_requests import StudyRequestService

router = APIRouter(prefix="/api/solicitudes-estudio", tags=["solicitudes de estudio"])

physician_roles = require_roles(UserRole.TREATING_PHYSICIAN, UserRole.SUPER_ADMIN)
reader_roles = require_roles(
    UserRole.TREATING_PHYSICIAN,
    UserRole.LAB_ADMINISTRATOR,
    UserRole.PATIENT,
    UserRole.SUPER_ADMIN,
)
# El detalle también lo ve bioinformática: necesita abrir el estudio de origen de un reanálisis.
detail_roles = require_roles(
    UserRole.TREATING_PHYSICIAN,
    UserRole.LAB_ADMINISTRATOR,
    UserRole.PATIENT,
    UserRole.BIOINFORMATICIAN,
    UserRole.SUPER_ADMIN,
)
admin_roles = require_roles(UserRole.LAB_ADMINISTRATOR, UserRole.SUPER_ADMIN)
patient_roles = require_roles(UserRole.PATIENT)
insurer_list_roles = require_roles(UserRole.PATIENT, UserRole.LAB_ADMINISTRATOR, UserRole.SUPER_ADMIN)

PDF_CONTENT_TYPE = "application/pdf"


class CreateStudyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    patient_id: PositiveInt
    pathology_codes: list[str] = Field(min_length=1, max_length=20)
    additional_genes: list[str] = Field(default_factory=list, max_length=200)
    include_secondary_findings: bool = False


class CreateReanalysisRequest(BaseModel):
    """Las patologías son opcionales: el médico puede pedir solo genes puntuales."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    pathology_codes: list[str] = Field(default_factory=list, max_length=20)
    additional_genes: list[str] = Field(default_factory=list, max_length=200)
    include_secondary_findings: bool = False


class PaymentModeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    mode: Literal["particular", "obra_social"]
    obra_social_id: str | None = Field(default=None, max_length=64)


class AuthorizeCoverageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    porcentaje: float | None = Field(default=None, ge=0, le=100)


class RejectCoverageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    motivo: str = Field(min_length=1, max_length=500)


class PayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    coupon_code: str | None = Field(default=None, max_length=64)


# --- Catálogo y selectores ---


@router.get("/catalogo")
async def pathology_catalog(
    _actor: AuthenticatedUser = Depends(physician_roles),
    service: StudyRequestService = Depends(get_study_request_service),
) -> list[dict[str, Any]]:
    try:
        return await service.catalogo()
    except HANDLED_ERRORS as exc:
        raise to_http_error(exc) from exc


@router.get("/genes")
async def search_genes(
    q: str = Query(min_length=1, max_length=50),
    _actor: AuthenticatedUser = Depends(physician_roles),
    service: StudyRequestService = Depends(get_study_request_service),
) -> list[str]:
    try:
        return await service.buscar_genes(q)
    except HANDLED_ERRORS as exc:
        raise to_http_error(exc) from exc


@router.get("/obras-sociales")
async def list_insurers(
    buscar: str | None = Query(default=None, max_length=100),
    _actor: AuthenticatedUser = Depends(insurer_list_roles),
    service: StudyPaymentService = Depends(get_study_payment_service),
) -> list[dict[str, Any]]:
    try:
        return await service.listar_obras_sociales(buscar)
    except HANDLED_ERRORS as exc:
        raise to_http_error(exc) from exc


# --- EC-10: solicitud ---


@router.post("", status_code=201)
async def create_study_request(
    body: CreateStudyRequest,
    actor: AuthenticatedUser = Depends(physician_roles),
    service: StudyRequestService = Depends(get_study_request_service),
) -> dict[str, Any]:
    try:
        return await service.crear(
            physician_id=actor.id,
            patient_id=body.patient_id,
            pathology_codes=body.pathology_codes,
            additional_genes=body.additional_genes,
            include_secondary_findings=body.include_secondary_findings,
        )
    except HANDLED_ERRORS as exc:
        raise to_http_error(exc) from exc


@router.get("")
def list_study_requests(
    actor: AuthenticatedUser = Depends(reader_roles),
    service: StudyRequestService = Depends(get_study_request_service),
) -> list[dict[str, Any]]:
    try:
        return service.listar(actor)
    except HANDLED_ERRORS as exc:
        raise to_http_error(exc) from exc


@router.get("/{study_id}")
def get_study_request(
    study_id: PositiveInt,
    actor: AuthenticatedUser = Depends(detail_roles),
    service: StudyRequestService = Depends(get_study_request_service),
) -> dict[str, Any]:
    try:
        return service.obtener(study_id, actor)
    except HANDLED_ERRORS as exc:
        raise to_http_error(exc) from exc


# --- EC-14: reanálisis ---


@router.post("/{study_id}/reanalisis", status_code=201)
async def request_reanalysis(
    study_id: PositiveInt,
    body: CreateReanalysisRequest,
    actor: AuthenticatedUser = Depends(physician_roles),
    service: StudyRequestService = Depends(get_study_request_service),
) -> dict[str, Any]:
    try:
        return await service.solicitar_reanalisis(
            study_id,
            actor,
            pathology_codes=body.pathology_codes,
            additional_genes=body.additional_genes,
            include_secondary_findings=body.include_secondary_findings,
        )
    except HANDLED_ERRORS as exc:
        raise to_http_error(exc) from exc


# --- EC-11: presupuesto ---


@router.post("/{study_id}/presupuesto", status_code=201)
def issue_budget(
    study_id: PositiveInt,
    actor: AuthenticatedUser = Depends(admin_roles),
    service: StudyRequestService = Depends(get_study_request_service),
) -> dict[str, Any]:
    try:
        return service.emitir_presupuesto(study_id, actor)
    except HANDLED_ERRORS as exc:
        raise to_http_error(exc) from exc


@router.get("/{study_id}/presupuesto")
def get_budget(
    study_id: PositiveInt,
    actor: AuthenticatedUser = Depends(reader_roles),
    service: StudyRequestService = Depends(get_study_request_service),
) -> dict[str, Any]:
    try:
        return service.obtener_presupuesto(study_id, actor)
    except HANDLED_ERRORS as exc:
        raise to_http_error(exc) from exc


# --- EC-13: modalidad de pago, cobertura y pago ---


@router.post("/{study_id}/modalidad-pago")
async def choose_payment_mode(
    study_id: PositiveInt,
    body: PaymentModeRequest,
    actor: AuthenticatedUser = Depends(patient_roles),
    service: StudyPaymentService = Depends(get_study_payment_service),
) -> dict[str, Any]:
    try:
        return await service.elegir_modalidad(study_id, actor, body.mode, body.obra_social_id)
    except HANDLED_ERRORS as exc:
        raise to_http_error(exc) from exc


@router.post("/{study_id}/cobertura/autorizar")
async def authorize_coverage(
    study_id: PositiveInt,
    body: AuthorizeCoverageRequest | None = None,
    actor: AuthenticatedUser = Depends(admin_roles),
    service: StudyPaymentService = Depends(get_study_payment_service),
) -> dict[str, Any]:
    try:
        percent = body.porcentaje if body is not None else None
        return await service.autorizar_cobertura(study_id, actor, percent)
    except HANDLED_ERRORS as exc:
        raise to_http_error(exc) from exc


@router.post("/{study_id}/cobertura/rechazar")
async def reject_coverage(
    study_id: PositiveInt,
    body: RejectCoverageRequest,
    actor: AuthenticatedUser = Depends(admin_roles),
    service: StudyPaymentService = Depends(get_study_payment_service),
) -> dict[str, Any]:
    try:
        return await service.rechazar_cobertura(study_id, actor, body.motivo)
    except HANDLED_ERRORS as exc:
        raise to_http_error(exc) from exc


@router.post("/{study_id}/cobertura/demanda")
async def submit_coverage_demand(
    study_id: PositiveInt,
    request: Request,
    filename: str | None = Query(default=None, max_length=200),
    actor: AuthenticatedUser = Depends(patient_roles),
    service: StudyPaymentService = Depends(get_study_payment_service),
) -> dict[str, Any]:
    """El PDF viaja como cuerpo crudo (Content-Type: application/pdf), sin multipart."""
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != PDF_CONTENT_TYPE:
        raise HTTPException(status_code=415, detail="Enviá el archivo como application/pdf.")
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_DEMAND_BYTES:
        raise HTTPException(status_code=413, detail="El PDF no puede superar los 5 MB.")
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_DEMAND_BYTES:
            raise HTTPException(status_code=413, detail="El PDF no puede superar los 5 MB.")
        chunks.append(chunk)
    try:
        return await service.presentar_demanda(study_id, actor, filename, b"".join(chunks))
    except HANDLED_ERRORS as exc:
        raise to_http_error(exc) from exc


@router.post("/{study_id}/pago")
async def pay_study(
    study_id: PositiveInt,
    body: PayRequest | None = None,
    actor: AuthenticatedUser = Depends(patient_roles),
    service: StudyPaymentService = Depends(get_study_payment_service),
) -> dict[str, Any]:
    try:
        coupon = body.coupon_code if body is not None else None
        return await service.pagar(study_id, actor, coupon)
    except HANDLED_ERRORS as exc:
        raise to_http_error(exc) from exc
