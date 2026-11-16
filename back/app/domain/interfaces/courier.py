from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Protocol


class PickupStatus(StrEnum):
    PROGRAMADO = "PROGRAMADO"
    RETIRADO = "RETIRADO"


class CourierError(Exception):
    """FedEx no respondió, rechazó el pedido o respondió algo que no se puede usar."""


class Courier(Protocol):
    # `fecha` con zona horaria; devuelve el UUID del retiro.
    def programar_retiro(self, lugar: str, fecha: datetime) -> str: ...

    def estado_retiro(self, uuid: str) -> PickupStatus: ...
