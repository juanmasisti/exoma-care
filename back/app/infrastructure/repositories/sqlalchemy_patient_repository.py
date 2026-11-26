from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, delete, func, insert, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.domain.entities.clinical_patient import PatientData
from app.domain.interfaces.patient_repository import PatientConflict
from app.infrastructure.database.models import Paciente, Usuario
from app.infrastructure.database.patient_clinical_models import (
    PatientClinicalRevision, patient_pathologies, patient_symptoms,
)


class SQLAlchemyPatientRepository:
    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def _scope(statement, physician_scope):
        return statement.where(Paciente.created_by_physician_id == physician_scope) if physician_scope is not None else statement

    def _record(self, patient, revision):
        snapshot = revision.snapshot if revision else {}
        data = snapshot.get("patient_data", {})
        email = patient.email or (patient.usuario.email if patient.usuario else "")
        return {"id": patient.id, "dni": patient.dni, "first_name": patient.nombre,
                "last_name": patient.apellido, "birth_date": patient.fecha_nacimiento,
                "phone": patient.telefono or "", "email": email,
                "clinical_summary": patient.clinical_summary or "",
                "suspicion_type": patient.suspicion_type, "family_history": patient.family_history or "",
                "pathology_ids": data.get("pathology_ids", []), "symptom_ids": data.get("symptom_ids", []),
                "suspicions": snapshot.get("suspicions", []), "symptoms": snapshot.get("symptoms", []),
                "version": patient.version, "created_by_physician_id": patient.created_by_physician_id,
                "access_status": "linked" if patient.usuario_id is not None else "pending",
                "created_at": patient.created_at, "updated_at": patient.updated_at,
                "clinical_record_complete": revision is not None}

    @staticmethod
    def _records_query():
        return select(Paciente, PatientClinicalRevision).outerjoin(
            PatientClinicalRevision, and_(PatientClinicalRevision.patient_id == Paciente.id,
                                         PatientClinicalRevision.version == Paciente.version))

    def get(self, patient_id: int, physician_scope: int | None) -> dict | None:
        row = self.session.execute(self._scope(self._records_query().where(Paciente.id == patient_id), physician_scope)).first()
        return self._record(*row) if row else None

    def list(self, physician_scope: int | None, query: str, limit: int, offset: int) -> dict:
        statement = self._scope(select(Paciente.id), physician_scope)
        query = query.strip().lower()
        if query:
            filters = [func.lower(Paciente.nombre).contains(query, autoescape=True),
                       func.lower(Paciente.apellido).contains(query, autoescape=True)]
            dni_query = query.replace(".", "").replace(" ", "")
            if dni_query:
                filters.append(Paciente.dni.contains(dni_query, autoescape=True))
            statement = statement.where(or_(*filters))
        total = self.session.scalar(select(func.count()).select_from(statement.subquery()))
        identifiers = statement.order_by(Paciente.apellido, Paciente.nombre, Paciente.id).limit(limit).offset(offset)
        rows = self.session.execute(self._records_query().where(Paciente.id.in_(identifiers))
                                    .order_by(Paciente.apellido, Paciente.nombre, Paciente.id)).all()
        summaries = []
        for patient, revision in rows:
            record = self._record(patient, revision)
            summaries.append({key: record[key] for key in ("id", "dni", "first_name", "last_name", "birth_date", "suspicion_type", "version", "access_status", "updated_at", "clinical_record_complete")}
                             | {"pathology_names": [s["name"] for s in record["suspicions"]]})
        return {"items": summaries, "total": total, "limit": limit, "offset": offset}

    def history(self, patient_id: int) -> list[dict]:
        revisions = self.session.execute(select(PatientClinicalRevision, Usuario).join(
            Usuario, Usuario.id == PatientClinicalRevision.changed_by_physician_id).where(
            PatientClinicalRevision.patient_id == patient_id).order_by(PatientClinicalRevision.version.desc()))
        return [{"version": r.version, "changed_at": r.changed_at,
                 "changed_by_physician_id": r.changed_by_physician_id,
                 "changed_by_name": f"{user.first_name} {user.last_name}", "snapshot": r.snapshot} for r, user in revisions]

    def save(self, data: PatientData, actor_id: int, snapshot: dict,
             patient_id: int | None, version: int | None) -> dict:
        duplicate = self.session.scalar(select(Paciente.id).where(Paciente.dni == data.dni))
        if duplicate is not None and duplicate != patient_id:
            raise PatientConflict("Ya existe un paciente con ese DNI.")
        patient = self.session.get(Paciente, patient_id) if patient_id is not None else Paciente()
        if patient is None:
            raise LookupError("El paciente no existe.")
        if patient_id is not None and patient.version != version:
            raise PatientConflict("Otra edición modificó el paciente. Recargá su ficha antes de guardar.")
        now = datetime.now(timezone.utc)
        patient.dni, patient.nombre, patient.apellido = data.dni, data.first_name, data.last_name
        patient.fecha_nacimiento, patient.telefono, patient.email = data.birth_date, data.phone, data.email
        patient.clinical_summary, patient.suspicion_type = data.clinical_summary, data.suspicion_type
        patient.family_history, patient.updated_at = data.family_history, now
        if patient_id is None:
            patient.created_by_physician_id, patient.created_at = actor_id, now
            # La cuenta se habilita en el circuito de identidad, no en el alta clínica.
            patient.usuario_id = None
        self.session.add(patient)
        try:
            self.session.flush()  # SQLAlchemy verifica/incrementa la versión al actualizar.
            for table, column, ids in ((patient_pathologies, "pathology_id", data.pathology_ids),
                                        (patient_symptoms, "symptom_id", data.symptom_ids)):
                self.session.execute(delete(table).where(table.c.patient_id == patient.id))
                if ids:
                    self.session.execute(insert(table), [{"patient_id": patient.id, column: id} for id in ids])
            self.session.add(PatientClinicalRevision(patient_id=patient.id, version=patient.version,
                changed_by_physician_id=actor_id, changed_at=now, snapshot=snapshot))
            self.session.commit()
        except StaleDataError:
            self.session.rollback()
            raise PatientConflict("Otra edición modificó el paciente. Recargá su ficha antes de guardar.") from None
        except IntegrityError:
            self.session.rollback()
            if self.session.scalar(select(Paciente.id).where(Paciente.dni == data.dni)) is not None:
                raise PatientConflict("No se pudo guardar: el DNI ya está registrado o hubo una edición simultánea.") from None
            raise
        return self.get(patient.id, None)
