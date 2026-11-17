"""Cupones de descuento (EC-12): el gerente los genera, el médico los reparte, el paciente los canjea.

La API de cupones guarda el estado real; acá se mantiene un espejo local para mostrar
listados, validar a quién pertenece cada cupón y conocer su porcentaje al pagar.
El canje ocurre dentro del pago (study_payments.py).
"""

from typing import Any

from app.domain.entities.roles import UserRole
from app.domain.entities.study_request import Coupon
from app.domain.entities.user import AuthenticatedUser
from app.domain.interfaces.coupon_gateway import CouponGateway
from app.domain.interfaces.study_request_repository import StudyRequestRepository
from app.infrastructure.external_services.errors import ExternalServiceError
from app.use_cases.study_request_errors import StudyRequestConflictError
from app.use_cases.study_request_views import NO_ACCESS_MESSAGE

MAX_BATCH_SIZE = 100


def physician_ref(user_id: int) -> str:
    """Id del médico ante la API de cupones: el id de su usuario en nuestra base."""
    return str(user_id)


def patient_ref(user_id: int) -> str:
    """Id del paciente ante la API de cupones: el id de su usuario en nuestra base."""
    return str(user_id)


def coupon_to_dict(coupon: Coupon) -> dict[str, Any]:
    return {
        "code": coupon.code,
        "percentage": coupon.percentage,
        "status": coupon.status,
        "physician_id": coupon.medico_id,
        "patient_id": coupon.patient_id,
        "generated_at": coupon.generated_at,
    }


class CouponService:
    def __init__(
        self,
        repo: StudyRequestRepository,
        gateway: CouponGateway,
        gerente_id: str,
    ):
        if not gerente_id.strip():
            raise ValueError("El id del gerente de cupones no puede estar vacío.")
        self._repo = repo
        self._gateway = gateway
        self._gerente_id = gerente_id.strip()

    async def generar_lote(
        self, cantidad: int, porcentaje_descuento: int | float
    ) -> list[dict[str, Any]]:
        if not 1 <= cantidad <= MAX_BATCH_SIZE:
            raise ValueError(f"La cantidad debe estar entre 1 y {MAX_BATCH_SIZE}.")
        if not 0 < porcentaje_descuento <= 100:
            raise ValueError("El descuento debe ser mayor que 0 y hasta 100.")
        items = await self._gateway.generar_lote(
            self._gerente_id, cantidad, porcentaje_descuento
        )
        try:
            created = [(str(item["codigo_cupon"]), float(item["porcentaje"])) for item in items]
        except (KeyError, TypeError, ValueError) as exc:
            raise ExternalServiceError(
                "Cupones", "La API devolvió un lote de cupones inválido.", 502
            ) from exc
        self._repo.add_coupons(created)
        self._repo.commit()
        return [
            coupon_to_dict(coupon)
            for coupon in (self._repo.get_coupon(code) for code, _ in created)
            if coupon is not None
        ]

    async def asignar_a_medico(self, codigo: str, medico_id: int) -> dict[str, Any]:
        coupon = self._coupon(codigo)
        if coupon.status != "disponible":
            raise StudyRequestConflictError("El cupón ya fue asignado o usado.")
        if not self._repo.physician_exists(medico_id):
            raise ValueError("El médico no existe.")
        await self._gateway.asignar_a_medico(
            self._gerente_id, physician_ref(medico_id), coupon.code
        )
        if not self._repo.assign_coupon_to_medico(coupon.code, medico_id):
            self._repo.rollback()
            raise StudyRequestConflictError("El cupón ya fue asignado o usado.")
        self._repo.commit()
        return coupon_to_dict(self._coupon(coupon.code))

    async def asignar_a_paciente(
        self, codigo: str, actor: AuthenticatedUser, patient_id: int
    ) -> dict[str, Any]:
        coupon = self._coupon(codigo)
        if coupon.medico_id != actor.id:
            raise PermissionError("El cupón no está asignado a este médico.")
        if coupon.status != "medico":
            raise StudyRequestConflictError("El cupón ya fue asignado a un paciente o usado.")
        if not self._repo.patient_exists(patient_id):
            raise LookupError("El paciente no existe.")
        patient_user_id = self._repo.user_id_for_patient(patient_id)
        if patient_user_id is None:
            raise ValueError(
                "El paciente todavía no tiene una cuenta de acceso: no se le puede asignar un cupón."
            )
        await self._gateway.asignar_a_paciente(
            physician_ref(actor.id), patient_ref(patient_user_id), coupon.code
        )
        if not self._repo.assign_coupon_to_patient(coupon.code, actor.id, patient_id):
            self._repo.rollback()
            raise StudyRequestConflictError("El cupón ya fue asignado a un paciente o usado.")
        self._repo.commit()
        return coupon_to_dict(self._coupon(coupon.code))

    def listar(
        self, actor: AuthenticatedUser, estado: str | None = None
    ) -> list[dict[str, Any]]:
        if actor.role in (UserRole.MEDICAL_MANAGER, UserRole.SUPER_ADMIN):
            coupons = self._repo.list_coupons(status=estado)
        elif actor.role is UserRole.TREATING_PHYSICIAN:
            coupons = self._repo.list_coupons(status=estado, medico_id=actor.id)
        elif actor.role is UserRole.PATIENT:
            patient_id = self._repo.patient_id_for_user(actor.id)
            coupons = (
                self._repo.list_coupons(status=estado, patient_id=patient_id)
                if patient_id is not None
                else []
            )
        else:
            raise PermissionError(NO_ACCESS_MESSAGE)
        return [coupon_to_dict(coupon) for coupon in coupons]

    def listar_medicos(self) -> list[dict[str, Any]]:
        return self._repo.list_physicians()

    def _coupon(self, codigo: str) -> Coupon:
        coupon = self._repo.get_coupon(codigo.strip())
        if coupon is None:
            raise LookupError("El cupón no existe.")
        return coupon
