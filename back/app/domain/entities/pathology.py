"""Reglas clínicas de una patología; sin dependencias de la API o la BD."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PathologyDefinition:
    name: str
    cardinal_symptom_id: int
    secondary_symptom_ids: frozenset[int]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("La patología requiere un nombre.")
        if self.cardinal_symptom_id in self.secondary_symptom_ids:
            raise ValueError("El síntoma cardinal no puede ser también secundario.")


@dataclass(frozen=True, slots=True)
class SuspicionValidation:
    valid: bool
    criterion: str
    matched_cardinal: bool
    matched_secondary_ids: tuple[int, ...]


def validate_clinical_suspicion(
    pathology: PathologyDefinition, symptom_ids: list[int]
) -> SuspicionValidation:
    """Valida una sospecha clínica, sin inferir un diagnóstico ni decidir un alta."""
    unique_ids = set(symptom_ids)
    cardinal = pathology.cardinal_symptom_id in unique_ids
    secondary = tuple(sorted(pathology.secondary_symptom_ids & unique_ids))
    criterion = "cardinal" if cardinal else (
        "two_secondary" if len(secondary) >= 2 else "insufficient_symptoms"
    )
    return SuspicionValidation(
        valid=cardinal or len(secondary) >= 2,
        criterion=criterion,
        matched_cardinal=cardinal,
        matched_secondary_ids=secondary,
    )
