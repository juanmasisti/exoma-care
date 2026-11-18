"""Antecedentes familiares: no constituyen altas de pacientes ni diagnósticos inferidos."""
from dataclasses import dataclass, replace

RELATIONSHIPS = ("mother", "father", "sibling", "child", "aunt_uncle", "grandparent", "cousin", "other")
PROVIDER_RELATIONSHIPS = {"mother": {1}, "father": {1}, "sibling": {2, 10, 11}, "child": {9},
    "aunt_uncle": {5, 6}, "grandparent": {3, 4}, "cousin": {7, 8}, "other": {12, 13, 14, 15}}

def validate_diagram_relationship(relationship, provider_relationship, sex):
    if provider_relationship is not None and provider_relationship not in PROVIDER_RELATIONSHIPS.get(relationship, set()):
        raise ValueError("El parentesco del familiograma no coincide con el antecedente familiar. Revisá ambos campos.")
    if (relationship == "mother" and sex == "hombre") or (relationship == "father" and sex == "mujer"):
        raise ValueError("El sexo seleccionado contradice el parentesco madre/padre. Revisá ambos campos.")

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

    first_name: str = ""
    last_name: str = ""
    provider_relationship: int | None = None
    sex: str = "no_identificado"
    age: float | None = None
    deceased: bool = False

    def normalized(self):
        return replace(self, first_name=self.first_name.strip(), last_name=self.last_name.strip(), full_name=" ".join(self.full_name.split()),
            relationship_detail=self.relationship_detail.strip(), notes=self.notes.strip(),
            symptom_ids=tuple(sorted(set(self.symptom_ids))), diagnosis_ids=tuple(sorted(set(self.diagnosis_ids))))

    def validate(self):
        validate_diagram_relationship(self.relationship, self.provider_relationship, self.sex)
        if self.provider_relationship is not None and self.provider_relationship not in range(1, 16):
            raise ValueError("El parentesco del familiograma debe ser un código de 1 a 15.")
        if self.sex not in ("hombre", "mujer", "no_identificado"):
            raise ValueError("Sexo del familiar inválido.")
        if self.age is not None and not 0 <= self.age <= 150:
            raise ValueError("La edad debe estar entre 0 y 150 años.")
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
