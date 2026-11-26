from app.domain.entities.pathology import (
    PathologyDefinition, SuspicionValidation, validate_clinical_suspicion,
)
from app.domain.interfaces.pathology_repository import Pathology, PathologyRepository


class PathologyCatalog:
    def __init__(self, repository: PathologyRepository):
        self.repository = repository

    def get(self, pathology_id: int) -> Pathology:
        pathology = self.repository.get_pathology(pathology_id)
        if pathology is None:
            raise LookupError("La patología no existe.")
        return pathology

    def save(self, name: str, cardinal_id: int | list[int], secondary_ids: list[int],
             pathology_id: int | None = None) -> Pathology:
        name = " ".join(name.split())
        cardinal_ids = list(dict.fromkeys(cardinal_id if isinstance(cardinal_id, list) else [cardinal_id]))
        if not cardinal_ids:
            raise ValueError("Seleccioná al menos un cardinal.")
        definition = PathologyDefinition(name, cardinal_ids[0], frozenset(secondary_ids), frozenset(cardinal_ids[1:]))
        if pathology_id is not None:
            self.get(pathology_id)
        self._require_symptoms({*cardinal_ids, *secondary_ids})
        return self.repository.save(definition, pathology_id)

    def validate(self, pathology_id: int, symptom_ids: list[int]) -> SuspicionValidation:
        pathology = self.get(pathology_id)
        self._require_symptoms(set(symptom_ids))
        return validate_clinical_suspicion(pathology.definition(), symptom_ids)

    def _require_symptoms(self, ids: set[int]) -> None:
        if not self.repository.symptom_ids_exist(ids):
            raise ValueError("Hay síntomas que no existen en el catálogo de terminología.")
