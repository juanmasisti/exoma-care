from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base


class StudyModel(Base):
    """PROVISORIO: mínimo para destrabar turnos; lo amplía el área de estudios (Tomás)."""

    __tablename__ = "studies"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    # String y no enum de base: Tomás puede sumar estados sin migrar datos.
    status: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
