from typing import Protocol


class FamilyConflict(ValueError):
    pass


class FamilyRepository(Protocol):
    def get(self, patient_id: int) -> dict: ...
    def history(self, patient_id: int) -> list[dict]: ...
    def save(self, patient_id: int, version: int, members: list[dict], actor_id: int) -> dict: ...
