from __future__ import annotations

from typing import Protocol


class StudyRepository(Protocol):
    def status(self, study_id: int) -> str | None: ...
    def set_status(self, study_id: int, status: str) -> bool: ...
