"""Enganches entre transporte (T04), lotes (T05) y envío (T06), para desarrollarlos por separado."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol


class SampleSetAssigner(Protocol):
    # Lo llama la llegada al laboratorio central por cada muestra recibida; lo implementa T05.
    def asignar_a_sample_set(self, sample_id: int, now: datetime) -> None: ...


class SampleSetClosedHandler(Protocol):
    # Lo llama el armado de lotes al cerrar uno; lo implementa T06 (CSV y autorización).
    def al_cerrar_lote(self, sample_set_id: int, now: datetime) -> None: ...
