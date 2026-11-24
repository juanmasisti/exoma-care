from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from app.domain.entities.roles import UserRole
from app.domain.entities.study import StudyStatus
from app.domain.entities.study_request import (
    Coupon,
    CoverageRequest,
    GeneRef,
    PathologyRef,
    StudyBudget,
    StudyRequest,
)


class DuplicateOperationError(RuntimeError):
    """Ya existe una operación financiera de ese tipo para el presupuesto."""


class StudyRequestRepository(Protocol):
    """Persistencia de solicitudes de estudio, presupuesto, cobertura, pagos y cupones.

    Ningún método confirma la transacción salvo commit(): el caso de uso decide cuándo,
    porque el pago con cupón necesita confirmar por etapas (decisión 008).
    """

    def commit(self) -> None: ...
    def rollback(self) -> None: ...

    # Pacientes y médicos
    def patient_exists(self, patient_id: int) -> bool: ...
    def patient_id_for_user(self, user_id: int) -> int | None: ...
    def patient_full_name(self, patient_id: int) -> str | None: ...
    def user_id_for_patient(self, patient_id: int) -> int | None: ...
    def physician_exists(self, user_id: int) -> bool: ...
    def list_physicians(self) -> list[dict[str, Any]]: ...
    def patient_physician_id(self, patient_id: int) -> int | None:
        """Médico que dio de alta al paciente (para estudios previos sin médico solicitante)."""
        ...

    # Destinatarios de avisos por mail
    def patient_email(self, patient_id: int) -> str | None:
        """Mail de la cuenta del paciente; si no tiene cuenta, el de su ficha."""
        ...
    def user_email(self, user_id: int) -> str | None: ...
    def emails_for_role(self, role: UserRole) -> list[str]: ...

    # Solicitudes de estudio
    def create_study(
        self,
        *,
        patient_id: int,
        physician_id: int,
        include_secondary_findings: bool,
        pathologies: Sequence[PathologyRef],
        genes: Sequence[GeneRef],
        original_study_id: int | None = None,
    ) -> StudyRequest: ...
    def get_study(self, study_id: int) -> StudyRequest | None: ...
    def get_bioinformatics_result(self, study_id: int) -> dict[str, Any] | None: ...
    def list_studies(
        self, *, physician_id: int | None = None, patient_id: int | None = None
    ) -> list[StudyRequest]: ...
    def list_reanalyses(self, study_id: int) -> list[StudyRequest]:
        """Reanálisis pedidos directamente sobre el estudio (EC-14)."""
        ...
    def transition_status(
        self, study_id: int, expected: StudyStatus, new: StudyStatus
    ) -> bool:
        """Cambia el estado solo si sigue siendo `expected` (evita carreras)."""
        ...

    # Presupuesto
    def create_budget(
        self,
        *,
        study_id: int,
        gene_count: int,
        base_cents: int,
        extra_genes: int,
        extra_cents: int,
        total_cents: int,
        currency: str,
        issued_by_user_id: int,
        discount_cents: int = 0,
    ) -> StudyBudget: ...
    def get_budget(self, study_id: int) -> StudyBudget | None: ...
    def update_budget(self, budget_id: int, **fields: Any) -> None:
        """Campos: payment_mode, insurer_external_id, insurer_name, coverage_percent,
        insurer_cents, patient_cents."""
        ...

    # Cobertura de obra social
    def create_coverage_request(
        self,
        *,
        budget_id: int,
        study_id: int,
        external_id: str,
        insurer_external_id: str,
        status: str,
        authorize_url: str,
        reject_url: str,
    ) -> CoverageRequest: ...
    def get_coverage_request(self, study_id: int) -> CoverageRequest | None: ...
    def update_coverage_request(self, coverage_id: int, **fields: Any) -> None:
        """Campos: status, rejection_reason, authorize_url, reject_url, resolved_at,
        demands_count."""
        ...
    def add_coverage_demand(
        self,
        *,
        coverage_id: int,
        filename: str,
        size_bytes: int,
        uploaded_by_user_id: int,
    ) -> None: ...

    # Registro financiero
    def register_operation(
        self,
        *,
        study_id: int,
        budget_id: int,
        patient_id: int,
        op_type: str,
        status: str,
        amount_cents: int,
        currency: str,
        discount_cents: int = 0,
        coupon_code: str | None = None,
        insurer_external_id: str | None = None,
        insurer_name: str | None = None,
        method: str | None = None,
        created_by_user_id: int | None = None,
    ) -> int:
        """Lanza DuplicateOperationError si ya hay una del mismo tipo para el presupuesto."""
        ...
    def update_operation(self, operation_id: int, **fields: Any) -> None:
        """Campos: status, amount_cents, discount_cents, coupon_code, method."""
        ...
    def delete_operation(self, operation_id: int) -> None: ...
    def list_operations(self, study_id: int) -> list[dict[str, Any]]: ...

    # Cupones (espejo local; la fuente de verdad del estado es la API de cupones)
    def add_coupons(self, coupons: Sequence[tuple[str, float]]) -> None: ...
    def get_coupon(self, code: str) -> Coupon | None: ...
    def list_coupons(
        self,
        *,
        status: str | None = None,
        medico_id: int | None = None,
        patient_id: int | None = None,
    ) -> list[Coupon]: ...
    def assign_coupon_to_medico(self, code: str, medico_id: int) -> bool: ...
    def assign_coupon_to_patient(self, code: str, medico_id: int, patient_id: int) -> bool: ...
    def claim_coupon(self, code: str, patient_id: int) -> bool:
        """paciente -> canjeando, de forma atómica. Solo uno de dos pedidos simultáneos gana."""
        ...
    def release_coupon(self, code: str, patient_id: int) -> bool: ...
    def mark_coupon_used(self, code: str, study_id: int | None) -> bool: ...
