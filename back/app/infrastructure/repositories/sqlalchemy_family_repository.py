from datetime import datetime, timezone

from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.domain.interfaces.family_repository import FamilyConflict
from app.infrastructure.database.models import Usuario
from app.infrastructure.database.family_models import (
    FamilyMemberModel, PatientFamilyRecord, PatientFamilyRevision,
    family_member_diagnoses, family_member_symptoms,
)


class SQLAlchemyFamilyRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, patient_id: int) -> dict:
        record = self.session.get(PatientFamilyRecord, patient_id)
        revision = self.session.get(PatientFamilyRevision, (patient_id, record.version)) if record else None
        return {"patient_id": patient_id, "version": record.version if record else 0,
                "members": revision.members if revision else [],
                "updated_at": record.updated_at if record else None,
                "familiogram_status": "not_configured"}

    def history(self, patient_id: int) -> list[dict]:
        rows = self.session.execute(select(PatientFamilyRevision, Usuario).join(
            Usuario, Usuario.id == PatientFamilyRevision.changed_by_physician_id).where(
            PatientFamilyRevision.patient_id == patient_id).order_by(PatientFamilyRevision.version.desc()))
        return [{"version": revision.version, "changed_at": revision.changed_at,
                 "changed_by_physician_id": user.id, "changed_by_name": f"{user.first_name} {user.last_name}",
                 "members": revision.members} for revision, user in rows]

    def save(self, patient_id: int, version: int, members: list[dict], actor_id: int) -> dict:
        record = self.session.get(PatientFamilyRecord, patient_id)
        if (record.version if record else 0) != version:
            raise FamilyConflict("Otro médico o pestaña modificó la información familiar. Recargá la familia antes de guardar.")
        now = datetime.now(timezone.utc)
        if record is None:
            record = PatientFamilyRecord(patient_id=patient_id)
        record.updated_at = now
        record.updated_by_physician_id = actor_id
        self.session.add(record)
        try:
            self.session.flush()  # También verifica la versión en la actualización.
            # La lista completa se reemplaza en una transacción; los snapshots anteriores permanecen.
            self.session.execute(delete(FamilyMemberModel).where(FamilyMemberModel.patient_id == patient_id))
            for position, data in enumerate(members):
                member = FamilyMemberModel(patient_id=patient_id, position=position,
                    **{key: data[key] for key in ("full_name", "relationship", "relationship_detail", "diagnosis_status", "notes")})
                self.session.add(member)
                self.session.flush()
                if data["symptom_ids"]:
                    self.session.execute(insert(family_member_symptoms), [{"member_id": member.id, "symptom_id": i} for i in data["symptom_ids"]])
                if data["diagnosis_ids"]:
                    self.session.execute(insert(family_member_diagnoses), [{"member_id": member.id, "pathology_id": i} for i in data["diagnosis_ids"]])
            self.session.add(PatientFamilyRevision(patient_id=patient_id, version=record.version,
                changed_by_physician_id=actor_id, changed_at=now, members=members))
            self.session.commit()
        except (StaleDataError, IntegrityError):
            self.session.rollback()
            raise FamilyConflict("No se pudo guardar por una modificación simultánea. Recargá la información familiar y revisá los cambios.") from None
        return self.get(patient_id)
