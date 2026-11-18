"""Modalidad de pago, cobertura de obra social y pago simulado (EC-13), con cupón (EC-12).

Reglas:
- La cobertura de la obra social se paga primero; el paciente abona el resto como si fuera
  particular. El cupón se aplica solo sobre lo que paga el paciente.
- Solo un estudio pagado o autorizado habilita el turno (ENABLED_STUDY_STATUSES).
- Pagar es una operación única por presupuesto: la reserva en el registro financiero
  (UNIQUE) hace de candado frente a pedidos simultáneos.
"""

from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import PurePath
from typing import Any

from app.domain.entities.study import StudyStatus

from app.domain.entities.budget import normalize_percent, split_amounts
from app.domain.entities.study_request import (
    MODE_CHANGE_ALLOWED_STATUSES,
    PAYMENT_MODES,
    STUDY_ID_REFERENCE_PREFIX,
    status_after_authorization,
    status_after_mode_choice,
    status_after_patient_payment,
)
from app.domain.entities.user import AuthenticatedUser
from app.domain.interfaces.coupon_gateway import CouponGateway
from app.domain.interfaces.insurance_gateway import InsuranceGateway
from app.domain.interfaces.study_request_repository import (
    DuplicateOperationError,
    StudyRequestRepository,
)
from app.infrastructure.external_services.errors import ExternalServiceError
from app.use_cases.coupons import patient_ref
from app.use_cases.study_request_errors import StudyRequestConflictError
from app.use_cases.study_request_views import (
    ensure_patient_owner,
    study_detail,
)

MAX_DEMAND_BYTES = 5 * 1024 * 1024  # límite de la API de obras sociales
MAX_REJECTION_REASON_LENGTH = 500
COUPON_REJECTED_STATUSES = frozenset({400, 404})  # 409 = ya usado


def _clean_percent(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral_value() else float(value)


def _clean_filename(filename: str | None) -> str:
    name = PurePath((filename or "").replace("\\", "/")).name.strip()[:120]
    if not name:
        return "demanda.pdf"
    return name if name.lower().endswith(".pdf") else f"{name}.pdf"


class StudyPaymentService:
    def __init__(
        self,
        repo: StudyRequestRepository,
        insurance: InsuranceGateway,
        coupons: CouponGateway,
        *,
        today: Callable[[], date] = date.today,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._repo = repo
        self._insurance = insurance
        self._coupons = coupons
        self._today = today
        self._now = now

    # --- Obras sociales (listado para el selector) ---

    async def listar_obras_sociales(self, buscar: str | None = None) -> list[dict[str, Any]]:
        return [
            {
                "id": item["id"],
                "name": item["nombre"],
                "acronym": item.get("sigla"),
                "rnos_code": item.get("rnos_codigo"),
                "default_coverage_percent": item.get("porcentaje_cobertura"),
            }
            for item in await self._insurance.listar_obras_sociales(buscar)
        ]

    # --- Modalidad de pago ---

    async def elegir_modalidad(
        self,
        study_id: int,
        actor: AuthenticatedUser,
        mode: str,
        obra_social_id: str | None = None,
    ) -> dict[str, Any]:
        study = self._study(study_id)
        patient_id = ensure_patient_owner(self._repo, study, actor)
        if mode not in PAYMENT_MODES:
            raise ValueError("La modalidad de pago debe ser 'particular' u 'obra_social'.")
        if study.status not in MODE_CHANGE_ALLOWED_STATUSES:
            raise StudyRequestConflictError(
                "La modalidad de pago ya fue elegida para este estudio."
            )
        budget = self._repo.get_budget(study_id)
        if budget is None:
            raise StudyRequestConflictError("El estudio todavía no tiene presupuesto.")

        if mode == "particular":
            self._repo.update_budget(
                budget.id,
                payment_mode="particular",
                insurer_external_id=None,
                insurer_name=None,
                coverage_percent=None,
                insurer_cents=0,
                patient_cents=budget.total_cents,
            )
        else:
            if study.status == StudyStatus.REJECTED:
                raise StudyRequestConflictError(
                    "La cobertura fue rechazada: presentá una demanda o pagá como particular."
                )
            if not obra_social_id:
                raise ValueError("Elegí una obra social.")
            insurer = await self._insurance.obtener_obra_social(obra_social_id)
            if insurer is None:
                raise ValueError("La obra social elegida no existe.")
            patient_name = self._repo.patient_full_name(patient_id)
            if not patient_name:
                raise LookupError("El paciente no existe.")
            request = await self._insurance.crear_solicitud(
                obra_social_id=insurer["id"],
                paciente_nombre=patient_name,
                fecha=self._today(),
                referencia_externa=f"{STUDY_ID_REFERENCE_PREFIX}{study_id}",
            )
            urls = request["urls_simulacion"]
            self._repo.create_coverage_request(
                budget_id=budget.id,
                study_id=study_id,
                external_id=request["id"],
                insurer_external_id=insurer["id"],
                status="pendiente",
                authorize_url=urls["autorizar"],
                reject_url=urls["rechazar"],
            )
            self._repo.update_budget(
                budget.id,
                payment_mode="obra_social",
                insurer_external_id=insurer["id"],
                insurer_name=insurer["nombre"],
                coverage_percent=insurer.get("porcentaje_cobertura"),
                insurer_cents=None,
                patient_cents=None,
            )

        self._transition(study_id, study.status, status_after_mode_choice(mode))
        self._repo.commit()
        return self._detail(study_id)

    # --- Cobertura: la gestiona el administrativo ---

    async def autorizar_cobertura(
        self,
        study_id: int,
        actor: AuthenticatedUser,
        porcentaje: int | float | None = None,
    ) -> dict[str, Any]:
        study = self._study(study_id)
        self._require_status(study, StudyStatus.PENDING_AUTHORIZATION)
        budget = self._repo.get_budget(study_id)
        coverage = self._repo.get_coverage_request(study_id)
        if budget is None or coverage is None:
            raise StudyRequestConflictError("El estudio no tiene una solicitud de cobertura.")

        requested = normalize_percent(porcentaje) if porcentaje is not None else None
        if coverage.status == "demanda_en_curso" and requested is None:
            raise ValueError(
                "Al autorizar una demanda hay que indicar el porcentaje de cobertura."
            )
        response = await self._insurance.autorizar(
            coverage.authorize_url,
            _clean_percent(requested) if requested is not None else None,
        )
        try:
            final_percent = normalize_percent(response["porcentaje_cobertura"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ExternalServiceError(
                "Obras sociales",
                "La API no devolvió un porcentaje de cobertura válido.",
                502,
            ) from exc

        split = split_amounts(budget.total_cents, final_percent)
        self._repo.update_budget(
            budget.id,
            coverage_percent=float(final_percent),
            insurer_cents=split.insurer_cents,
            patient_cents=split.patient_gross_cents,
        )
        self._repo.update_coverage_request(
            coverage.id, status="autorizada", resolved_at=self._now()
        )
        if split.insurer_cents > 0:
            try:
                self._repo.register_operation(
                    study_id=study_id,
                    budget_id=budget.id,
                    patient_id=study.patient_id,
                    op_type="cobertura_obra_social",
                    status="a_cobrar",
                    amount_cents=split.insurer_cents,
                    currency=budget.currency,
                    insurer_external_id=budget.insurer_external_id,
                    insurer_name=budget.insurer_name,
                    created_by_user_id=actor.id,
                )
            except DuplicateOperationError as exc:
                self._repo.rollback()
                raise StudyRequestConflictError(
                    "La cobertura de este estudio ya está registrada."
                ) from exc
        self._transition(
            study_id,
            StudyStatus.PENDING_AUTHORIZATION,
            status_after_authorization(split.patient_gross_cents),
        )
        self._repo.commit()
        return self._detail(study_id)

    async def rechazar_cobertura(
        self, study_id: int, actor: AuthenticatedUser, motivo: str
    ) -> dict[str, Any]:
        study = self._study(study_id)
        self._require_status(study, StudyStatus.PENDING_AUTHORIZATION)
        reason = (motivo or "").strip()
        if not reason:
            raise ValueError("Indicá el motivo del rechazo.")
        if len(reason) > MAX_REJECTION_REASON_LENGTH:
            raise ValueError(
                f"El motivo no puede superar los {MAX_REJECTION_REASON_LENGTH} caracteres."
            )
        coverage = self._repo.get_coverage_request(study_id)
        if coverage is None:
            raise StudyRequestConflictError("El estudio no tiene una solicitud de cobertura.")

        await self._insurance.rechazar(coverage.reject_url, reason)
        self._repo.update_coverage_request(
            coverage.id,
            status="rechazada",
            rejection_reason=reason,
            resolved_at=self._now(),
        )
        self._transition(
            study_id,
            StudyStatus.PENDING_AUTHORIZATION,
            StudyStatus.REJECTED,
        )
        self._repo.commit()
        return self._detail(study_id)

    async def presentar_demanda(
        self,
        study_id: int,
        actor: AuthenticatedUser,
        filename: str | None,
        content: bytes,
    ) -> dict[str, Any]:
        """El paciente adjunta el PDF de la demanda tras un rechazo y pide reautorización."""
        study = self._study(study_id)
        ensure_patient_owner(self._repo, study, actor)
        self._require_status(study, StudyStatus.REJECTED)
        if not content:
            raise ValueError("El archivo está vacío.")
        if len(content) > MAX_DEMAND_BYTES:
            raise ValueError("El PDF no puede superar los 5 MB.")
        if not content.startswith(b"%PDF"):
            raise ValueError("El archivo debe ser un PDF.")
        coverage = self._repo.get_coverage_request(study_id)
        if coverage is None or coverage.status != "rechazada":
            raise StudyRequestConflictError(
                "Solo se puede presentar una demanda sobre una cobertura rechazada."
            )

        name = _clean_filename(filename)
        response = await self._insurance.presentar_demanda(coverage.external_id, name, content)
        fields: dict[str, Any] = {
            "status": "demanda_en_curso",
            "demands_count": coverage.demands_count + 1,
        }
        urls = response.get("urls_simulacion") if isinstance(response, dict) else None
        if (
            isinstance(urls, dict)
            and isinstance(urls.get("autorizar"), str)
            and isinstance(urls.get("rechazar"), str)
        ):
            fields["authorize_url"] = urls["autorizar"]
            fields["reject_url"] = urls["rechazar"]
        self._repo.update_coverage_request(coverage.id, **fields)
        self._repo.add_coverage_demand(
            coverage_id=coverage.id,
            filename=name,
            size_bytes=len(content),
            uploaded_by_user_id=actor.id,
        )
        self._transition(
            study_id,
            StudyStatus.REJECTED,
            StudyStatus.PENDING_AUTHORIZATION,
        )
        self._repo.commit()
        return self._detail(study_id)

    # --- Pago simulado del paciente (con cupón opcional) ---

    async def pagar(
        self,
        study_id: int,
        actor: AuthenticatedUser,
        coupon_code: str | None = None,
    ) -> dict[str, Any]:
        study = self._study(study_id)
        patient_id = ensure_patient_owner(self._repo, study, actor)
        self._require_status(study, StudyStatus.PENDING_PAYMENT)
        budget = self._repo.get_budget(study_id)
        if budget is None or budget.payment_mode is None or budget.patient_cents is None:
            raise StudyRequestConflictError("Todavía no está definido el importe a pagar.")

        code = (coupon_code or "").strip() or None
        coupon = None
        if code is not None:
            coupon = self._repo.get_coupon(code)
            if coupon is None or coupon.status != "paciente" or coupon.patient_id != patient_id:
                raise ValueError("El cupón no existe o no está asignado a este paciente.")

        split = split_amounts(
            budget.total_cents,
            budget.coverage_percent or 0,
            coupon.percentage if coupon is not None else 0,
        )
        if split.patient_gross_cents != budget.patient_cents:
            raise StudyRequestConflictError(
                "El importe del estudio cambió: volvé a consultar el presupuesto."
            )

        # Etapa A: reservar el pago. El UNIQUE (presupuesto, tipo) deja pasar un solo pedido.
        try:
            operation_id = self._repo.register_operation(
                study_id=study_id,
                budget_id=budget.id,
                patient_id=patient_id,
                op_type="cobro_paciente",
                status="registrando",
                amount_cents=split.patient_cents,
                discount_cents=split.discount_cents,
                coupon_code=code,
                currency=budget.currency,
                method="simulado",
                insurer_external_id=budget.insurer_external_id,
                insurer_name=budget.insurer_name,
                created_by_user_id=actor.id,
            )
        except DuplicateOperationError as exc:
            self._repo.rollback()
            raise StudyRequestConflictError(
                "Ya hay un pago registrado o en curso para este estudio."
            ) from exc
        self._repo.commit()

        # Etapa B: canjear el cupón. Se reserva localmente antes de avisar a la API.
        if code is not None:
            if not self._repo.claim_coupon(code, patient_id):
                self._discard_operation(operation_id)
                raise StudyRequestConflictError("El cupón ya no está disponible.")
            self._repo.commit()
            try:
                await self._coupons.canjear(patient_ref(actor.id), code)
            except ExternalServiceError as exc:
                if exc.status_code == 409:
                    self._repo.mark_coupon_used(code, None)
                    self._discard_operation(operation_id)
                    raise StudyRequestConflictError(str(exc)) from exc
                if exc.status_code in COUPON_REJECTED_STATUSES:
                    self._repo.release_coupon(code, patient_id)
                    self._discard_operation(operation_id)
                    raise ValueError(str(exc)) from exc
                # Resultado incierto (timeout, 503): no se repite la escritura. El cupón y el
                # pago quedan reservados hasta verificar el estado del cupón en la API.
                raise

        # Etapa C: confirmar el pago y habilitar el estudio.
        self._repo.update_operation(operation_id, status="registrada")
        if code is not None:
            self._repo.mark_coupon_used(code, study_id)
        self._transition(
            study_id,
            StudyStatus.PENDING_PAYMENT,
            status_after_patient_payment(budget.payment_mode),
        )
        self._repo.commit()
        return self._detail(study_id)

    # --- Internos ---

    def _discard_operation(self, operation_id: int) -> None:
        self._repo.delete_operation(operation_id)
        self._repo.commit()

    def _transition(
        self, study_id: int, expected: StudyStatus, new: StudyStatus
    ) -> None:
        if not self._repo.transition_status(study_id, expected, new):
            self._repo.rollback()
            raise StudyRequestConflictError(
                "El estado del estudio cambió mientras se procesaba la operación."
            )

    def _require_status(self, study, expected: StudyStatus) -> None:
        if study.status != expected:
            raise StudyRequestConflictError(
                f"La operación requiere un estudio en estado '{expected.value}' "
                f"(estado actual: '{study.status.value}')."
            )

    def _study(self, study_id: int):
        study = self._repo.get_study(study_id)
        if study is None:
            raise LookupError("El estudio no existe.")
        return study

    def _detail(self, study_id: int) -> dict[str, Any]:
        return study_detail(self._repo, self._study(study_id))
