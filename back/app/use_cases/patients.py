from dataclasses import asdict

from app.domain.entities.clinical_patient import PatientData, evaluate_suspicions
from app.domain.interfaces.patient_repository import PatientRepository
from app.domain.interfaces.pathology_repository import PathologyRepository


class ClinicalValidationError(ValueError):
    def __init__(self, results):
        super().__init__("Todas las sospechas clínicas seleccionadas deben cumplir los criterios antes de guardar.")
        self.results = results


class PatientClinicalService:
    def __init__(self, patients: PatientRepository, catalog: PathologyRepository):
        self.patients = patients
        self.catalog = catalog

    def evaluate(self, data: PatientData) -> tuple[PatientData, dict]:
        data = data.normalized()
        data.validate_fields()
        pathologies = []
        for identifier in data.pathology_ids:
            pathology = self.catalog.get_pathology(identifier)
            if pathology is None:
                raise ValueError("Hay patologías seleccionadas que no existen en el catálogo.")
            pathologies.append(pathology)
        symptoms = self.catalog.get_symptoms(set(data.symptom_ids))
        if {s.id for s in symptoms} != set(data.symptom_ids):
            raise ValueError("Hay síntomas que no existen en el catálogo de terminología.")
        results = evaluate_suspicions(data, pathologies)
        snapshot_data = asdict(data)
        snapshot_data["birth_date"] = data.birth_date.isoformat()
        snapshot = {"patient_data": snapshot_data, "symptoms": [asdict(s) for s in symptoms],
                    "suspicions": [{**result, "definition": asdict(pathology)}
                                   for result, pathology in zip(results, pathologies)]}
        return data, {"valid": all(r["valid"] for r in results), "results": results, "snapshot": snapshot}

    def get(self, patient_id: int, physician_scope: int | None) -> dict:
        record = self.patients.get(patient_id, physician_scope)
        if record is None:
            raise LookupError("El paciente no existe o no está disponible para tu perfil.")
        return record

    def save(self, data: PatientData, actor_id: int, physician_scope: int | None,
             patient_id: int | None = None, version: int | None = None) -> dict:
        if patient_id is not None:
            self.get(patient_id, physician_scope)
        data, evaluation = self.evaluate(data)
        if not evaluation["valid"]:
            raise ClinicalValidationError(evaluation["results"])
        return self.patients.save(data, actor_id, evaluation["snapshot"], patient_id, version)
