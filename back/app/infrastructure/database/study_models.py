from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SQLAlchemyEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.entities.study import STUDY_STATUSES, StudyStatus
from app.infrastructure.database.session import Base


class StudyModel(Base):
    """PROVISORIO: mínimo para destrabar turnos; lo amplía el área de estudios (Tomás)."""

    __tablename__ = "studies"
    __table_args__ = (
        CheckConstraint(
            "status IN (" + ", ".join(f"'{status}'" for status in STUDY_STATUSES) + ")",
            name="ck_studies_status_valid",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    analyst_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    status: Mapped[StudyStatus] = mapped_column(
        SQLAlchemyEnum(
            StudyStatus,
            name="study_status",
            native_enum=False,
            create_constraint=False,
            values_callable=lambda statuses: [status.value for status in statuses],
            length=40,
        )
    )
    codigo_patologia: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Médico que pidió el estudio (EC-10). Nulo en estudios anteriores a la solicitud.
    physician_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_studies_physician_id_users"), nullable=True, index=True
    )
    include_secondary_findings: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0"
    )
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    variantes_detectadas: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True
    )
    resultado_diagnostico: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    hallazgos_secundarios: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True
    )
    fecha_reevaluacion: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


def _now() -> datetime:
    return datetime.now(UTC)


class StudyPathologyModel(Base):
    """Patologías elegidas en la solicitud (código y nombre de Apigen al momento del pedido)."""

    __tablename__ = "study_pathologies"
    __table_args__ = (UniqueConstraint("study_id", "code", name="uq_study_pathologies_study_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    study_id: Mapped[int] = mapped_column(ForeignKey("studies.id"), index=True)
    code: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(200))


class StudyGeneModel(Base):
    """Genes a analizar; el mismo gen no puede repetirse dentro de un estudio."""

    __tablename__ = "study_genes"
    __table_args__ = (UniqueConstraint("study_id", "symbol", name="uq_study_genes_study_symbol"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    study_id: Mapped[int] = mapped_column(ForeignKey("studies.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(50))
    origin: Mapped[str] = mapped_column(String(20))  # catalogo | manual


class StudyBudgetModel(Base):
    """Presupuesto del estudio. Importes en centavos enteros (sin Decimal en la base)."""

    __tablename__ = "study_budgets"
    __table_args__ = (UniqueConstraint("study_id", name="uq_study_budgets_study"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    study_id: Mapped[int] = mapped_column(ForeignKey("studies.id"))
    gene_count: Mapped[int] = mapped_column(Integer)
    base_cents: Mapped[int] = mapped_column(Integer)
    extra_genes: Mapped[int] = mapped_column(Integer)
    extra_cents: Mapped[int] = mapped_column(Integer)
    total_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    issued_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    payment_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    insurer_external_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    insurer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    coverage_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    insurer_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    patient_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)


class CoverageRequestModel(Base):
    """Solicitud de cobertura creada en la API de obras sociales."""

    __tablename__ = "coverage_requests"
    __table_args__ = (
        UniqueConstraint("budget_id", name="uq_coverage_requests_budget"),
        UniqueConstraint("study_id", name="uq_coverage_requests_study"),
        UniqueConstraint("external_id", name="uq_coverage_requests_external_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    budget_id: Mapped[int] = mapped_column(ForeignKey("study_budgets.id"))
    study_id: Mapped[int] = mapped_column(ForeignKey("studies.id"))
    external_id: Mapped[str] = mapped_column(String(64))
    insurer_external_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30))
    # Las URLs de simulación son una credencial: nunca se exponen en la API propia.
    authorize_url: Mapped[str] = mapped_column(String(500))
    reject_url: Mapped[str] = mapped_column(String(500))
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    demands_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CoverageDemandModel(Base):
    """Constancia de cada PDF de demanda presentado (el archivo vive en la API de obras sociales)."""

    __tablename__ = "coverage_demands"

    id: Mapped[int] = mapped_column(primary_key=True)
    coverage_id: Mapped[int] = mapped_column(ForeignKey("coverage_requests.id"), index=True)
    filename: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    uploaded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class FinancialOperationModel(Base):
    """Registro financiero. UNIQUE (presupuesto, tipo): hace de candado contra pagos dobles."""

    __tablename__ = "financial_operations"
    __table_args__ = (
        UniqueConstraint("budget_id", "type", name="uq_financial_operations_budget_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    study_id: Mapped[int] = mapped_column(ForeignKey("studies.id"), index=True)
    budget_id: Mapped[int] = mapped_column(ForeignKey("study_budgets.id"))
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20))
    amount_cents: Mapped[int] = mapped_column(Integer)
    discount_cents: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    coupon_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    currency: Mapped[str] = mapped_column(String(3))
    method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    insurer_external_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    insurer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CouponModel(Base):
    """Espejo local de los cupones; el estado real vive en la API de cupones."""

    __tablename__ = "coupons"
    __table_args__ = (UniqueConstraint("code", name="uq_coupons_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64))
    percentage: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), index=True)
    medico_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"), nullable=True, index=True)
    redeemed_study_id: Mapped[int | None] = mapped_column(ForeignKey("studies.id"), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
