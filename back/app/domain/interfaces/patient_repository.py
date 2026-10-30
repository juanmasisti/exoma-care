from __future__ import annotations

from typing import Protocol

from app.domain.entities.clinical_patient import PatientData


class PatientConflict(ValueError):
    """DNI duplicado o versión desactualizada; la operación no se confirma."""


class PatientRepository(Protocol):
    def get(self, patient_id: int, physician_scope: int | None) -> dict | None: ...
    def list(self, physician_scope: int | None, query: str, limit: int, offset: int) -> dict: ...
    def history(self, patient_id: int) -> list[dict]: ...
    def save(self, data: PatientData, actor_id: int, snapshot: dict,
             patient_id: int | None, version: int | None) -> dict: ...
