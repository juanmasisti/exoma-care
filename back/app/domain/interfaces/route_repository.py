from __future__ import annotations

from datetime import date
from typing import Protocol


class RouteAlreadyExists(Exception):
    """El índice único (date, province_id) rechazó la orden: esa provincia ya tiene orden ese día."""


class RouteRepository(Protocol):
    # Orden con sus paradas en secuencia: {id, date, province_id, transporter_id, status, arrived_at, stops}.
    def get(self, route_id: int) -> dict | None: ...
    def route_for(self, day: date, province_id: int) -> dict | None: ...
    # Las paradas toman la secuencia 1..n en el orden recibido; devuelve el id de la orden.
    def add_route(self, day: date, province_id: int, transporter_id: int | None, center_ids: list[int]) -> int: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
