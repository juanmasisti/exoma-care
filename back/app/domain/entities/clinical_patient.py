"""Datos clínicos y política de sospechas confirmada para EC-07."""
from dataclasses import dataclass
from datetime import date
import re

from app.domain.interfaces.pathology_repository import Pathology
from app.domain.entities.pathology import validate_clinical_suspicion


@dataclass(frozen=True, slots=True)
class PatientData:
    dni: str
    first_name: str
    last_name: str
    birth_date: date
    phone: str
    email: str
    clinical_summary: str
    suspicion_type: str
    family_history: str
    pathology_ids: tuple[int, ...]
    symptom_ids: tuple[int, ...]

    def normalized(self):
        return PatientData(
            self.dni.replace(".", "").replace(" ", ""),
            " ".join(self.first_name.split()), " ".join(self.last_name.split()),
            self.birth_date, self.phone.strip(), self.email.strip().lower(),
            self.clinical_summary.strip(), self.suspicion_type, self.family_history.strip(),
            tuple(sorted(set(self.pathology_ids))), tuple(sorted(set(self.symptom_ids))),
        )

    def validate_fields(self):
        if not re.fullmatch(r"[0-9]{1,20}", self.dni):
            raise ValueError("El DNI debe contener números; se admiten puntos o espacios de presentación.")
        if not all((self.first_name, self.last_name, self.phone, self.email, self.clinical_summary)):
            raise ValueError("Completá los datos personales y el resumen de historia clínica.")
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", self.email):
            raise ValueError("El email no tiene un formato válido.")
        if self.birth_date > date.today():
            raise ValueError("La fecha de nacimiento no puede ser futura.")
        if self.suspicion_type not in ("clinical", "family"):
            raise ValueError("Indicá si la sospecha es clínica o familiar.")
        if not self.pathology_ids:
            raise ValueError("Seleccioná al menos una patología sospechada.")
        if self.suspicion_type == "family" and not self.family_history:
            raise ValueError("La sospecha familiar requiere un antecedente documentado.")


def evaluate_suspicions(data: PatientData, pathologies: list[Pathology]) -> list[dict]:
    """No persiste. Mantiene resultados individuales de todas las sospechas."""
    results = []
    for pathology in pathologies:
        if data.suspicion_type == "family":
            results.append({"pathology_id": pathology.id, "name": pathology.name,
                            "valid": bool(data.family_history.strip()), "criterion": "family_history",
                            "matched_cardinal": False, "matched_secondary_ids": []})
        else:
            result = validate_clinical_suspicion(pathology.definition(), list(data.symptom_ids))
            results.append({"pathology_id": pathology.id, "name": pathology.name,
                            "valid": result.valid, "criterion": result.criterion,
                            "matched_cardinal": result.matched_cardinal,
                            "matched_secondary_ids": list(result.matched_secondary_ids)})
    return results
