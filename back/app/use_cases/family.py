from dataclasses import asdict

from app.domain.entities.family import FamilyMemberData
from app.domain.interfaces.family_repository import FamilyRepository
from app.domain.interfaces.patient_repository import PatientRepository
from app.domain.interfaces.pathology_repository import PathologyRepository


class PatientFamilyService:
    def __init__(self, family: FamilyRepository, patients: PatientRepository, catalog: PathologyRepository):
        self.family, self.patients, self.catalog = family, patients, catalog

    def require_patient(self, patient_id: int):
        if self.patients.get(patient_id, None) is None:
            raise LookupError("El paciente no existe.")

    def get(self, patient_id: int):
        self.require_patient(patient_id)
        return self.family.get(patient_id)

    def history(self, patient_id: int):
        self.require_patient(patient_id)
        return self.family.history(patient_id)

    def save(self, patient_id: int, version: int, members: list[FamilyMemberData], actor_id: int):
        self.require_patient(patient_id)
        records = []
        for member in members:
            member = member.normalized()
            member.validate()
            symptoms = self.catalog.get_symptoms(set(member.symptom_ids))
            if {s.id for s in symptoms} != set(member.symptom_ids):
                raise ValueError("Hay síntomas del familiar que no existen en el catálogo.")
            diagnoses = []
            for identifier in member.diagnosis_ids:
                pathology = self.catalog.get_pathology(identifier)
                if pathology is None:
                    raise ValueError("Hay diagnósticos del familiar que no existen en el catálogo de patologías.")
                diagnoses.append({"id": pathology.id, "name": pathology.name})
            records.append({**asdict(member), "symptoms": [asdict(s) for s in symptoms], "diagnoses": diagnoses})
        return self.family.save(patient_id, version, records, actor_id)
