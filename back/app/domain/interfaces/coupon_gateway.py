from __future__ import annotations

from typing import Any, Protocol


class CouponGateway(Protocol):
    """API de cupones (otro grupo). Los ids de actores son strings que elegimos nosotros.

    Ante un error, las implementaciones lanzan ExternalServiceError: 400/404/409 son
    rechazos definitivos del negocio; cualquier otro código (503, timeout) deja el
    resultado de la operación como incierto.
    """

    async def generar_lote(
        self, gerente_id: str, cantidad: int, porcentaje_descuento: int | float
    ) -> list[dict[str, Any]]:
        """Devuelve [{"codigo_cupon": str, "porcentaje": number}, ...]."""
        ...

    async def asignar_a_medico(
        self, gerente_id: str, medico_id: str, codigo: str
    ) -> None: ...

    async def asignar_a_paciente(
        self, medico_id: str, paciente_id: str, codigo: str
    ) -> None: ...

    async def canjear(self, paciente_id: str, codigo: str) -> None: ...
