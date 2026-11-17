from datetime import date, datetime, timezone

from sqlalchemy import exists, select, update
from app.domain.entities.family import validate_diagram_relationship
from app.domain.interfaces.family_repository import FamilyConflict
from app.infrastructure.database.models import Paciente
from app.infrastructure.database.family_models import PatientFamilyRecord, FamiliogramDocument
from app.infrastructure.external_services.familiogram_client import svg_pdf
from app.infrastructure.repositories.sqlalchemy_family_repository import SQLAlchemyFamilyRepository
from app.infrastructure.repositories.sqlalchemy_patient_repository import SQLAlchemyPatientRepository
from app.infrastructure.repositories.sqlalchemy_pathology_repository import SQLAlchemyPathologyRepository


def symptoms(records):
    # Keep historical DEMO identity explicit: never mislabel it as SNOMED.
    return [{"codigo": str(s["code"]) if s["code_system"] == "SNOMED" else f"{s['code_system']}:{s['code']}", "nombre": s["label"]} for s in records]


def build_payload(patient, family, catalog):
    person = {"parentesco": 0, "nombre": patient["first_name"], "apellido": patient["last_name"],
              "sexo": "no_identificado", "sintomas": symptoms(patient["symptoms"]), "diagnosticos": []}
    if patient.get("birth_date"):
        born = patient["birth_date"]
        today = date.today()
        person["edad"] = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    people = [person]
    for index, member in enumerate(family["members"], 1):
        if not member.get("first_name") or not member.get("last_name") or member.get("provider_relationship") not in range(1, 16):
            raise ValueError(f"Completá nombre, apellido y parentesco del familiograma del familiar {index}. No se dividen nombres históricos automáticamente.")
        validate_diagram_relationship(member["relationship"], member["provider_relationship"], member.get("sex", "no_identificado"))
        diagnoses = []
        if member["diagnosis_status"] == "known":
            for diagnosis in member.get("diagnoses", []):
                pathology = catalog.get_pathology(diagnosis["id"])
                code = pathology.apigen_code if pathology else None
                if not code:
                    code = f"EXOMA:{diagnosis['id']}"
                diagnoses.append({"codigo": code, "nombre": diagnosis["name"]})
        people.append({"parentesco": member["provider_relationship"], "nombre": member["first_name"], "apellido": member["last_name"],
                       "sexo": member.get("sex", "no_identificado"), "edad": member.get("age"), "fallecido": member.get("deceased", False),
                       "sintomas": symptoms(member.get("symptoms", [])), "diagnosticos": diagnoses})
    return {"personas": people, "opciones": {"reglaSospecha": "desactivada"}}


class FamiliogramService:
    def __init__(self, session, client):
        self.session, self.client = session, client
        self.patients = SQLAlchemyPatientRepository(session)
        self.family = SQLAlchemyFamilyRepository(session)
        self.catalog = SQLAlchemyPathologyRepository(session)

    def patient(self, patient_id):
        patient = self.patients.get(patient_id, None)
        if patient is None:
            raise LookupError("El paciente no existe.")
        return patient

    def metadata(self, row, patient_version, family_version):
        return {"id": row.id, "patient_version": row.patient_version, "family_version": row.family_version,
                "created_at": row.created_at, "created_by_physician_id": row.created_by_physician_id,
                "warnings": row.warnings, "stale": row.patient_version != patient_version or row.family_version != family_version}

    def list(self, patient_id):
        patient, family = self.patient(patient_id), self.family.get(patient_id)
        rows = self.session.scalars(select(FamiliogramDocument).where(FamiliogramDocument.patient_id == patient_id).order_by(FamiliogramDocument.id.desc())).all()
        return [self.metadata(row, patient["version"], family["version"]) for row in rows]

    def generate(self, patient_id, patient_version, family_version, actor_id):
        patient, family = self.patient(patient_id), self.family.get(patient_id)
        if (patient["version"], family["version"]) != (patient_version, family_version):
            raise FamilyConflict("La ficha o la familia cambió. Recargá antes de generar.")
        payload = build_payload(patient, family, self.catalog)
        self.session.rollback()  # No read transaction retained during network/conversion.
        svg, warnings = self.client.generate(payload)
        pdf = svg_pdf(svg)
        # Conditional write takes the database write lock. Both source versions must still match.
        family_check = exists(select(PatientFamilyRecord.patient_id).where(PatientFamilyRecord.patient_id == patient_id, PatientFamilyRecord.version == family_version)) if family_version else ~exists(select(PatientFamilyRecord.patient_id).where(PatientFamilyRecord.patient_id == patient_id))
        matched = self.session.execute(update(Paciente).where(Paciente.id == patient_id, Paciente.version == patient_version, family_check).values(version=Paciente.version), execution_options={"synchronize_session": False})
        if matched.rowcount != 1:
            self.session.rollback()
            raise FamilyConflict("La ficha o la familia cambió durante la generación. Generá nuevamente con la versión actual.")
        row = FamiliogramDocument(patient_id=patient_id, patient_version=patient_version, family_version=family_version,
            created_by_physician_id=actor_id, created_at=datetime.now(timezone.utc), svg=svg, pdf=pdf, warnings=warnings)
        self.session.add(row)
        self.session.commit()
        return self.metadata(row, patient_version, family_version)

    def document(self, patient_id, document_id):
        self.patient(patient_id)
        row = self.session.scalar(select(FamiliogramDocument).where(FamiliogramDocument.id == document_id, FamiliogramDocument.patient_id == patient_id))
        if row is None:
            raise LookupError("El documento no existe para este paciente.")
        return row
