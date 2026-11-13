from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class MinistryAuthorization:
    status: str  # "autorizado"
    pdf: bytes


class HealthMinistry(Protocol):
    # Recibe el CSV con los pacientes del lote.
    def solicitar_autorizacion(self, csv: str) -> MinistryAuthorization: ...
