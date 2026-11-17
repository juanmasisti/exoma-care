from __future__ import annotations

from datetime import date
from typing import Any, Protocol


class InsuranceGateway(Protocol):
    """API de obras sociales (Grupo 9). Lanza ExternalServiceError ante cualquier falla."""

    async def listar_obras_sociales(self, buscar: str | None = None) -> list[dict[str, Any]]:
        """Todas las obras sociales: id, rnos_codigo, nombre, sigla, porcentaje_cobertura."""
        ...

    async def obtener_obra_social(self, obra_social_id: str) -> dict[str, Any] | None: ...

    async def crear_solicitud(
        self,
        *,
        obra_social_id: str,
        paciente_nombre: str,
        fecha: date,
        referencia_externa: str,
    ) -> dict[str, Any]:
        """Solicitud en estado pendiente, con urls_simulacion {autorizar, rechazar}."""
        ...

    async def autorizar(self, url: str, porcentaje: int | float | None = None) -> dict[str, Any]: ...

    async def rechazar(self, url: str, motivo: str) -> dict[str, Any]: ...

    async def presentar_demanda(
        self, solicitud_id: str, filename: str, content: bytes
    ) -> dict[str, Any]: ...
