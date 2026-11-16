from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base


class StudyModel(Base):
    """PROVISORIO: mínimo para destrabar turnos; lo amplía el área de estudios (Tomás)."""

    __tablename__ = "studies"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    analyst_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    # String y no enum de base: Tomás puede sumar estados sin migrar datos.
    status: Mapped[str] = mapped_column(String(40))
    codigo_patologia: Mapped[str | None] = mapped_column(String(100), nullable=True)
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
