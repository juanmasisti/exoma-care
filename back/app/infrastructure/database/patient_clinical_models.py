from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, Table
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base

patient_pathologies = Table(
    "patient_pathologies", Base.metadata,
    Column("patient_id", ForeignKey("patients.id", ondelete="CASCADE"), primary_key=True),
    Column("pathology_id", ForeignKey("pathologies.id"), primary_key=True),
)
patient_symptoms = Table(
    "patient_symptoms", Base.metadata,
    Column("patient_id", ForeignKey("patients.id", ondelete="CASCADE"), primary_key=True),
    Column("symptom_id", ForeignKey("symptoms.id"), primary_key=True),
)


class PatientClinicalRevision(Base):
    __tablename__ = "patient_clinical_revisions"

    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    changed_by_physician_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    snapshot: Mapped[dict] = mapped_column(JSON)
