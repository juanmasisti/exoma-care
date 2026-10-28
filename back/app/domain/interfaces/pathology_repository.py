from dataclasses import dataclass
from typing import Protocol

from app.domain.entities.pathology import PathologyDefinition


@dataclass(frozen=True, slots=True)
class Symptom:
    id: int
    code: str
    label: str
    code_system: str


@dataclass(frozen=True, slots=True)
class Pathology:
    id: int
    name: str
    cardinal_symptom: Symptom
    secondary_symptoms: tuple[Symptom, ...]

    def definition(self) -> PathologyDefinition:
        return PathologyDefinition(
            self.name, self.cardinal_symptom.id,
            frozenset(s.id for s in self.secondary_symptoms),
        )


class DuplicatePathologyName(ValueError):
    pass


class PathologyRepository(Protocol):
    def list_pathologies(self) -> list[Pathology]: ...
    def get_pathology(self, pathology_id: int) -> Pathology | None: ...
    def list_symptoms(self, query: str) -> list[Symptom]: ...
    def symptom_ids_exist(self, ids: set[int]) -> bool: ...
    def save(self, definition: PathologyDefinition, pathology_id: int | None) -> Pathology: ...
