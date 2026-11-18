"""Persistencia SQLAlchemy de solicitudes, presupuesto, cobertura, pagos y cupones (EC-10 a EC-13).

Nada confirma la transacción salvo commit(). Los cambios de estado que compiten entre pedidos
simultáneos (estado del estudio, cupones) son UPDATE condicionales: gana quien cambia la fila.
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.entities.study import StudyStatus

from app.domain.entities.roles import UserRole
from app.domain.entities.study_request import (
    Coupon,
    CoverageRequest,
    GeneRef,
    PathologyRef,
    StudyBudget,
    StudyRequest,
)
from app.domain.interfaces.study_request_repository import DuplicateOperationError
from app.infrastructure.database.models import Paciente, Usuario
from app.infrastructure.database.study_models import (
    CouponModel,
    CoverageDemandModel,
    CoverageRequestModel,
    FinancialOperationModel,
    StudyBudgetModel,
    StudyGeneModel,
    StudyModel,
    StudyPathologyModel,
)

BUDGET_FIELDS = frozenset(
    {
        "payment_mode",
        "insurer_external_id",
        "insurer_name",
        "coverage_percent",
        "insurer_cents",
        "patient_cents",
    }
)
COVERAGE_FIELDS = frozenset(
    {"status", "rejection_reason", "authorize_url", "reject_url", "resolved_at", "demands_count"}
)
OPERATION_FIELDS = frozenset({"status", "amount_cents", "discount_cents", "coupon_code", "method"})

_FRESH = {"populate_existing": True}


def _checked(fields: dict[str, Any], allowed: frozenset[str]) -> dict[str, Any]:
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"Campos no permitidos: {sorted(unknown)}")
    return fields


class SqlAlchemyStudyRequestRepository:
    def __init__(self, session: Session):
        self._session = session

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()

    # --- Pacientes y médicos ---

    def patient_exists(self, patient_id: int) -> bool:
        return self._session.get(Paciente, patient_id) is not None

    def patient_id_for_user(self, user_id: int) -> int | None:
        return self._session.scalar(select(Paciente.id).where(Paciente.usuario_id == user_id))

    def patient_full_name(self, patient_id: int) -> str | None:
        patient = self._session.get(Paciente, patient_id)
        return f"{patient.nombre} {patient.apellido}".strip() if patient else None

    def user_id_for_patient(self, patient_id: int) -> int | None:
        return self._session.scalar(select(Paciente.usuario_id).where(Paciente.id == patient_id))

    def physician_exists(self, user_id: int) -> bool:
        return (
            self._session.scalar(
                select(Usuario.id).where(
                    Usuario.id == user_id, Usuario.role == UserRole.TREATING_PHYSICIAN
                )
            )
            is not None
        )

    def list_physicians(self) -> list[dict[str, Any]]:
        rows = self._session.execute(
            select(Usuario)
            .where(Usuario.role == UserRole.TREATING_PHYSICIAN)
            .order_by(Usuario.last_name, Usuario.first_name)
        ).scalars()
        return [
            {
                "id": user.id,
                "name": f"{user.first_name} {user.last_name}".strip(),
                "specialty": user.specialty,
                "license_number": user.license_number,
            }
            for user in rows
        ]

    # --- Solicitudes de estudio ---

    def create_study(
        self,
        *,
        patient_id: int,
        physician_id: int,
        include_secondary_findings: bool,
        pathologies: Sequence[PathologyRef],
        genes: Sequence[GeneRef],
    ) -> StudyRequest:
        study = StudyModel(
            patient_id=patient_id,
            physician_id=physician_id,
            status=StudyStatus.CREATED,
            include_secondary_findings=include_secondary_findings,
        )
        self._session.add(study)
        self._session.flush()
        self._session.add_all(
            StudyPathologyModel(study_id=study.id, code=item.code, name=item.name)
            for item in pathologies
        )
        self._session.add_all(
            StudyGeneModel(study_id=study.id, symbol=gene.symbol, origin=gene.origin)
            for gene in genes
        )
        self._session.flush()
        return self._study(study)

    def get_study(self, study_id: int) -> StudyRequest | None:
        study = self._session.execute(
            select(StudyModel).where(StudyModel.id == study_id).execution_options(**_FRESH)
        ).scalar_one_or_none()
        return self._study(study) if study else None

    def get_bioinformatics_result(self, study_id: int) -> dict[str, Any] | None:
        study = self._session.get(StudyModel, study_id)
        if study is None or study.status != StudyStatus.RESULT_AVAILABLE:
            return None
        return {
            "status": study.status,
            "codigo_patologia": study.codigo_patologia,
            "resultado_diagnostico": study.resultado_diagnostico,
            "variantes_detectadas": study.variantes_detectadas or [],
            "hallazgos_secundarios": study.hallazgos_secundarios or [],
            "fecha_reevaluacion": (
                study.fecha_reevaluacion.isoformat()
                if study.fecha_reevaluacion
                else None
            ),
        }

    def list_studies(
        self, *, physician_id: int | None = None, patient_id: int | None = None
    ) -> list[StudyRequest]:
        query = select(StudyModel)
        if physician_id is not None:
            query = query.where(StudyModel.physician_id == physician_id)
        elif patient_id is None:
            # Las vistas administrativas muestran solicitudes, no registros históricos.
            query = query.where(StudyModel.physician_id.is_not(None))
        if patient_id is not None:
            query = query.where(StudyModel.patient_id == patient_id)
        rows = self._session.execute(
            query.order_by(StudyModel.id.desc()).execution_options(**_FRESH)
        ).scalars()
        return [self._study(study) for study in rows]

    def transition_status(
        self, study_id: int, expected: StudyStatus, new: StudyStatus
    ) -> bool:
        result = self._session.execute(
            update(StudyModel)
            .where(StudyModel.id == study_id, StudyModel.status == expected)
            .values(status=new)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1

    def _study(self, study: StudyModel) -> StudyRequest:
        pathologies = self._session.execute(
            select(StudyPathologyModel)
            .where(StudyPathologyModel.study_id == study.id)
            .order_by(StudyPathologyModel.id)
            .execution_options(**_FRESH)
        ).scalars()
        genes = self._session.execute(
            select(StudyGeneModel)
            .where(StudyGeneModel.study_id == study.id)
            .order_by(StudyGeneModel.id)
            .execution_options(**_FRESH)
        ).scalars()
        return StudyRequest(
            id=study.id,
            patient_id=study.patient_id,
            physician_id=study.physician_id,
            status=study.status,
            include_secondary_findings=bool(study.include_secondary_findings),
            created_at=study.created_at,
            pathologies=tuple(PathologyRef(p.code, p.name) for p in pathologies),
            genes=tuple(GeneRef(g.symbol, g.origin) for g in genes),
        )

    # --- Presupuesto ---

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
    ) -> StudyBudget:
        budget = StudyBudgetModel(
            study_id=study_id,
            gene_count=gene_count,
            base_cents=base_cents,
            extra_genes=extra_genes,
            extra_cents=extra_cents,
            total_cents=total_cents,
            currency=currency,
            issued_by_user_id=issued_by_user_id,
        )
        self._session.add(budget)
        self._session.flush()
        return self._budget(budget)

    def get_budget(self, study_id: int) -> StudyBudget | None:
        budget = self._session.execute(
            select(StudyBudgetModel)
            .where(StudyBudgetModel.study_id == study_id)
            .execution_options(**_FRESH)
        ).scalar_one_or_none()
        return self._budget(budget) if budget else None

    def update_budget(self, budget_id: int, **fields: Any) -> None:
        self._session.execute(
            update(StudyBudgetModel)
            .where(StudyBudgetModel.id == budget_id)
            .values(**_checked(fields, BUDGET_FIELDS))
            .execution_options(synchronize_session=False)
        )

    @staticmethod
    def _budget(model: StudyBudgetModel) -> StudyBudget:
        return StudyBudget(
            id=model.id,
            study_id=model.study_id,
            gene_count=model.gene_count,
            base_cents=model.base_cents,
            extra_genes=model.extra_genes,
            extra_cents=model.extra_cents,
            total_cents=model.total_cents,
            currency=model.currency,
            issued_by_user_id=model.issued_by_user_id,
            issued_at=model.issued_at,
            payment_mode=model.payment_mode,
            insurer_external_id=model.insurer_external_id,
            insurer_name=model.insurer_name,
            coverage_percent=model.coverage_percent,
            insurer_cents=model.insurer_cents,
            patient_cents=model.patient_cents,
        )

    # --- Cobertura ---

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
    ) -> CoverageRequest:
        coverage = CoverageRequestModel(
            budget_id=budget_id,
            study_id=study_id,
            external_id=external_id,
            insurer_external_id=insurer_external_id,
            status=status,
            authorize_url=authorize_url,
            reject_url=reject_url,
        )
        self._session.add(coverage)
        self._session.flush()
        return self._coverage(coverage)

    def get_coverage_request(self, study_id: int) -> CoverageRequest | None:
        coverage = self._session.execute(
            select(CoverageRequestModel)
            .where(CoverageRequestModel.study_id == study_id)
            .execution_options(**_FRESH)
        ).scalar_one_or_none()
        return self._coverage(coverage) if coverage else None

    def update_coverage_request(self, coverage_id: int, **fields: Any) -> None:
        self._session.execute(
            update(CoverageRequestModel)
            .where(CoverageRequestModel.id == coverage_id)
            .values(**_checked(fields, COVERAGE_FIELDS))
            .execution_options(synchronize_session=False)
        )

    def add_coverage_demand(
        self, *, coverage_id: int, filename: str, size_bytes: int, uploaded_by_user_id: int
    ) -> None:
        self._session.add(
            CoverageDemandModel(
                coverage_id=coverage_id,
                filename=filename,
                size_bytes=size_bytes,
                uploaded_by_user_id=uploaded_by_user_id,
            )
        )
        self._session.flush()

    @staticmethod
    def _coverage(model: CoverageRequestModel) -> CoverageRequest:
        return CoverageRequest(
            id=model.id,
            budget_id=model.budget_id,
            study_id=model.study_id,
            external_id=model.external_id,
            insurer_external_id=model.insurer_external_id,
            status=model.status,
            authorize_url=model.authorize_url,
            reject_url=model.reject_url,
            demands_count=model.demands_count,
            created_at=model.created_at,
            rejection_reason=model.rejection_reason,
            resolved_at=model.resolved_at,
        )

    # --- Registro financiero ---

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
        already = self._session.scalar(
            select(FinancialOperationModel.id).where(
                FinancialOperationModel.budget_id == budget_id,
                FinancialOperationModel.type == op_type,
            )
        )
        if already is not None:
            raise DuplicateOperationError(op_type)
        operation = FinancialOperationModel(
            study_id=study_id,
            budget_id=budget_id,
            patient_id=patient_id,
            type=op_type,
            status=status,
            amount_cents=amount_cents,
            discount_cents=discount_cents,
            coupon_code=coupon_code,
            currency=currency,
            method=method,
            insurer_external_id=insurer_external_id,
            insurer_name=insurer_name,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(operation)
        try:
            self._session.flush()
        except IntegrityError as exc:
            # El UNIQUE (presupuesto, tipo) frenó un pedido simultáneo que pasó la verificación.
            raise DuplicateOperationError(op_type) from exc
        return operation.id

    def update_operation(self, operation_id: int, **fields: Any) -> None:
        self._session.execute(
            update(FinancialOperationModel)
            .where(FinancialOperationModel.id == operation_id)
            .values(**_checked(fields, OPERATION_FIELDS))
            .execution_options(synchronize_session=False)
        )

    def delete_operation(self, operation_id: int) -> None:
        operation = self._session.get(FinancialOperationModel, operation_id)
        if operation is not None:
            self._session.delete(operation)
            self._session.flush()

    def list_operations(self, study_id: int) -> list[dict[str, Any]]:
        rows = self._session.execute(
            select(FinancialOperationModel)
            .where(FinancialOperationModel.study_id == study_id)
            .order_by(FinancialOperationModel.id)
            .execution_options(**_FRESH)
        ).scalars()
        return [
            {
                "id": op.id,
                "type": op.type,
                "status": op.status,
                "amount_cents": op.amount_cents,
                "discount_cents": op.discount_cents,
                "coupon_code": op.coupon_code,
                "currency": op.currency,
                "method": op.method,
                "insurer_external_id": op.insurer_external_id,
                "insurer_name": op.insurer_name,
                "created_at": op.created_at,
            }
            for op in rows
        ]

    # --- Cupones ---

    def add_coupons(self, coupons: Sequence[tuple[str, float]]) -> None:
        self._session.add_all(
            CouponModel(code=code, percentage=percentage, status="disponible")
            for code, percentage in coupons
        )
        self._session.flush()

    def get_coupon(self, code: str) -> Coupon | None:
        coupon = self._session.execute(
            select(CouponModel).where(CouponModel.code == code).execution_options(**_FRESH)
        ).scalar_one_or_none()
        return self._coupon(coupon) if coupon else None

    def list_coupons(
        self,
        *,
        status: str | None = None,
        medico_id: int | None = None,
        patient_id: int | None = None,
    ) -> list[Coupon]:
        query = select(CouponModel)
        if status is not None:
            query = query.where(CouponModel.status == status)
        if medico_id is not None:
            query = query.where(CouponModel.medico_id == medico_id)
        if patient_id is not None:
            query = query.where(CouponModel.patient_id == patient_id)
        rows = self._session.execute(
            query.order_by(CouponModel.id).execution_options(**_FRESH)
        ).scalars()
        return [self._coupon(coupon) for coupon in rows]

    def assign_coupon_to_medico(self, code: str, medico_id: int) -> bool:
        return self._conditional_coupon_update(
            [CouponModel.code == code, CouponModel.status == "disponible"],
            status="medico",
            medico_id=medico_id,
        )

    def assign_coupon_to_patient(self, code: str, medico_id: int, patient_id: int) -> bool:
        return self._conditional_coupon_update(
            [
                CouponModel.code == code,
                CouponModel.status == "medico",
                CouponModel.medico_id == medico_id,
            ],
            status="paciente",
            patient_id=patient_id,
        )

    def claim_coupon(self, code: str, patient_id: int) -> bool:
        return self._conditional_coupon_update(
            [
                CouponModel.code == code,
                CouponModel.status == "paciente",
                CouponModel.patient_id == patient_id,
            ],
            status="canjeando",
        )

    def release_coupon(self, code: str, patient_id: int) -> bool:
        return self._conditional_coupon_update(
            [
                CouponModel.code == code,
                CouponModel.status == "canjeando",
                CouponModel.patient_id == patient_id,
            ],
            status="paciente",
        )

    def mark_coupon_used(self, code: str, study_id: int | None) -> bool:
        return self._conditional_coupon_update(
            [CouponModel.code == code, CouponModel.status.in_(("canjeando", "paciente"))],
            status="usado",
            redeemed_study_id=study_id,
        )

    def _conditional_coupon_update(self, conditions: list[Any], **values: Any) -> bool:
        result = self._session.execute(
            update(CouponModel)
            .where(*conditions)
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1

    @staticmethod
    def _coupon(model: CouponModel) -> Coupon:
        return Coupon(
            code=model.code,
            percentage=model.percentage,
            status=model.status,
            generated_at=model.generated_at,
            medico_id=model.medico_id,
            patient_id=model.patient_id,
        )
