from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base


class PatientFamilyRecord(Base):
    __tablename__ = "patient_family_records"
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_by_physician_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    __mapper_args__ = {"version_id_col": version}


class FamilyMemberModel(Base):
    __tablename__ = "family_members"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patient_family_records.patient_id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    full_name: Mapped[str] = mapped_column(String(200))
    relationship: Mapped[str] = mapped_column(String(32))
    relationship_detail: Mapped[str] = mapped_column(String(100))
    diagnosis_status: Mapped[str] = mapped_column(String(16))
    notes: Mapped[str] = mapped_column(Text)


family_member_symptoms = Table("family_member_symptoms", Base.metadata,
    Column("member_id", ForeignKey("family_members.id", ondelete="CASCADE"), primary_key=True),
    Column("symptom_id", ForeignKey("symptoms.id"), primary_key=True))
family_member_diagnoses = Table("family_member_diagnoses", Base.metadata,
    Column("member_id", ForeignKey("family_members.id", ondelete="CASCADE"), primary_key=True),
    Column("pathology_id", ForeignKey("pathologies.id"), primary_key=True))


class PatientFamilyRevision(Base):
    __tablename__ = "patient_family_revisions"
    patient_id: Mapped[int] = mapped_column(ForeignKey("patient_family_records.patient_id", ondelete="CASCADE"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    changed_by_physician_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    members: Mapped[list] = mapped_column(JSON)
