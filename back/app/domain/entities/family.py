"""Antecedentes familiares: no constituyen altas de pacientes ni diagnósticos inferidos."""
from dataclasses import dataclass, replace

RELATIONSHIPS = ("mother", "father", "sibling", "child", "aunt_uncle", "grandparent", "cousin", "other")
DIAGNOSIS_STATUSES = ("unknown", "none", "known")


@dataclass(frozen=True, slots=True)
class FamilyMemberData:
    full_name: str
    relationship: str
    relationship_detail: str
    symptom_ids: tuple[int, ...]
    diagnosis_status: str
    diagnosis_ids: tuple[int, ...]
    notes: str

    def normalized(self):
        return replace(self, full_name=" ".join(self.full_name.split()),
            relationship_detail=self.relationship_detail.strip(), notes=self.notes.strip(),
            symptom_ids=tuple(sorted(set(self.symptom_ids))), diagnosis_ids=tuple(sorted(set(self.diagnosis_ids))))

    def validate(self):
        if not self.full_name:
            raise ValueError("Completá el nombre de cada familiar.")
        if self.relationship not in RELATIONSHIPS:
            raise ValueError("El parentesco seleccionado no es válido.")
        if self.relationship == "other" and not self.relationship_detail:
            raise ValueError("Aclará el parentesco al seleccionar Otro.")
        if self.diagnosis_status not in DIAGNOSIS_STATUSES:
            raise ValueError("Indicá si existe información sobre diagnósticos del familiar.")
        if self.diagnosis_status == "known" and not self.diagnosis_ids:
            raise ValueError("Seleccioná al menos una patología para un diagnóstico conocido.")
        if self.diagnosis_status != "known" and self.diagnosis_ids:
            raise ValueError("Solo se pueden asociar patologías cuando hay un diagnóstico conocido.")
