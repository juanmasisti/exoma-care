"""Tablas del catálogo; no se mezclan con los datos clínicos del paciente."""

from sqlalchemy import Column, ForeignKey, String, Table, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.session import Base


pathology_secondary_symptoms = Table(
    "pathology_secondary_symptoms", Base.metadata,
    Column("pathology_id", ForeignKey("pathologies.id", ondelete="CASCADE"), primary_key=True),
    Column("symptom_id", ForeignKey("symptoms.id"), primary_key=True),
)


pathology_additional_cardinals = Table(
    "pathology_additional_cardinals", Base.metadata,
    Column("pathology_id", ForeignKey("pathologies.id", ondelete="CASCADE"), primary_key=True),
    Column("symptom_id", ForeignKey("symptoms.id"), primary_key=True),
)


class SymptomModel(Base):
    __tablename__ = "symptoms"
    __table_args__ = (UniqueConstraint("code_system", "code", name="uq_symptom_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(100))
    label: Mapped[str] = mapped_column(String(200))
    code_system: Mapped[str] = mapped_column(String(50))


class PathologyModel(Base):
    __tablename__ = "pathologies"
    __table_args__ = (UniqueConstraint("apigen_code", "apigen_group", name="uq_pathology_apigen_identity"),)

    apigen_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    apigen_group: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cdss_code: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    normalized_name: Mapped[str] = mapped_column(String(160), unique=True)
    cardinal_symptom_id: Mapped[int] = mapped_column(ForeignKey("symptoms.id"))
    cardinal_symptom: Mapped[SymptomModel] = relationship(foreign_keys=[cardinal_symptom_id])
    additional_cardinal_symptoms: Mapped[list[SymptomModel]] = relationship(
        secondary=pathology_additional_cardinals, order_by=SymptomModel.id,
    )
    secondary_symptoms: Mapped[list[SymptomModel]] = relationship(
        secondary=pathology_secondary_symptoms, order_by=SymptomModel.id,
    )
