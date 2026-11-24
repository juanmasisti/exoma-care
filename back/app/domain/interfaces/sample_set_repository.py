from __future__ import annotations

from datetime import datetime
from typing import Protocol


class AssemblingSetExists(Exception):
    """El índice único parcial rechazó el lote: ya hay uno armándose."""


class SlotTaken(Exception):
    """Otra muestra ganó ese lugar del lote: probar con el siguiente."""


class SampleAlreadyInSet(Exception):
    """La muestra ya pertenece a un lote."""


class SetFull(Exception):
    """El lugar pedido está fuera de 1..10: el lote no tiene más lugar, hay que abrir otro."""


class SetNotAssembling(Exception):
    """El lote ya no se está armando (lo cerró otro pedido o no existe): un lote cerrado no cambia."""


class SampleSetRepository(Protocol):
    # Lote con sus muestras: {id, status, is_urgent, created_at, closed_at, items: [{slot, sample_id}]}.
    def get(self, sample_set_id: int) -> dict | None: ...
    def assembling(self) -> dict | None: ...
    def open_set(self, is_urgent: bool, now: datetime) -> int: ...
    def add_item(self, sample_set_id: int, sample_id: int, slot: int) -> None: ...
    # Condicional: solo cierra un lote que sigue armándose; devuelve si lo cerró.
    def close(self, sample_set_id: int, now: datetime, is_urgent: bool = False) -> bool: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
