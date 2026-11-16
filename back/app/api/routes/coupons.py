"""Cupones de descuento (EC-12): gerente -> médico -> paciente."""

from typing import Any

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from app.api.catalog_dependencies import require_roles
from app.api.study_dependencies import get_coupon_service
from app.api.study_http import HANDLED_ERRORS, to_http_error
from app.domain.entities.roles import UserRole
from app.domain.entities.user import AuthenticatedUser
from app.use_cases.coupons import MAX_BATCH_SIZE, CouponService

router = APIRouter(prefix="/api/cupones", tags=["cupones"])

manager_roles = require_roles(UserRole.MEDICAL_MANAGER, UserRole.SUPER_ADMIN)
physician_roles = require_roles(UserRole.TREATING_PHYSICIAN)
reader_roles = require_roles(
    UserRole.MEDICAL_MANAGER,
    UserRole.TREATING_PHYSICIAN,
    UserRole.PATIENT,
    UserRole.SUPER_ADMIN,
)

CouponCode = Path(min_length=1, max_length=64)


class BatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cantidad: int = Field(ge=1, le=MAX_BATCH_SIZE)
    porcentaje_descuento: float = Field(gt=0, le=100)


class AssignPhysicianRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    medico_id: PositiveInt


class AssignPatientRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_id: PositiveInt


@router.post("/lote", status_code=201)
async def generate_batch(
    body: BatchRequest,
    _actor: AuthenticatedUser = Depends(manager_roles),
    service: CouponService = Depends(get_coupon_service),
) -> list[dict[str, Any]]:
    try:
        return await service.generar_lote(body.cantidad, body.porcentaje_descuento)
    except HANDLED_ERRORS as exc:
        raise to_http_error(exc) from exc


@router.get("/medicos")
def list_physicians(
    _actor: AuthenticatedUser = Depends(manager_roles),
    service: CouponService = Depends(get_coupon_service),
) -> list[dict[str, Any]]:
    return service.listar_medicos()


@router.post("/{codigo}/asignar-medico")
async def assign_to_physician(
    body: AssignPhysicianRequest,
    codigo: str = CouponCode,
    _actor: AuthenticatedUser = Depends(manager_roles),
    service: CouponService = Depends(get_coupon_service),
) -> dict[str, Any]:
    try:
        return await service.asignar_a_medico(codigo, body.medico_id)
    except HANDLED_ERRORS as exc:
        raise to_http_error(exc) from exc


@router.post("/{codigo}/asignar-paciente")
async def assign_to_patient(
    body: AssignPatientRequest,
    codigo: str = CouponCode,
    actor: AuthenticatedUser = Depends(physician_roles),
    service: CouponService = Depends(get_coupon_service),
) -> dict[str, Any]:
    try:
        return await service.asignar_a_paciente(codigo, actor, body.patient_id)
    except HANDLED_ERRORS as exc:
        raise to_http_error(exc) from exc


@router.get("")
def list_coupons(
    estado: str | None = Query(
        default=None, pattern="^(disponible|medico|paciente|canjeando|usado)$"
    ),
    actor: AuthenticatedUser = Depends(reader_roles),
    service: CouponService = Depends(get_coupon_service),
) -> list[dict[str, Any]]:
    try:
        return service.listar(actor, estado)
    except HANDLED_ERRORS as exc:
        raise to_http_error(exc) from exc
