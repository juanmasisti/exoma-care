from __future__ import annotations

from typing import Protocol

Point = tuple[float, float]  # (latitud, longitud)


class RouteOptimizerError(Exception):
    """El módulo de recorridos no respondió o respondió algo que no se puede usar."""


class RouteOptimizer(Protocol):
    # El primer y el último punto quedan fijos (partida y destino); solo se ordenan los del medio.
    def order(self, points: list[Point]) -> list[Point]: ...
