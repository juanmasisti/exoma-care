"""Cliente de la API de cupones (otro grupo). Implementa CouponGateway.

Las escrituras nunca se reintentan: ante un timeout el resultado es incierto y repetir un
canje o una asignación podría duplicarlo. Los 400/403/404/409 son rechazos definitivos.
"""

from typing import Any

import httpx

from app.infrastructure.external_services.errors import ExternalServiceError

SERVICE = "Cupones"
DEFAULT_BASE_URL = "https://vekuhonbpqtzakqbcoph.supabase.co/functions/v1/cupones-api"


class CuponesClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        if not api_key or not api_key.strip():
            raise ValueError("La API key de cupones no puede estar vacía.")
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport

    async def generar_lote(
        self, gerente_id: str, cantidad: int, porcentaje_descuento: int | float
    ) -> list[dict[str, Any]]:
        body = await self._post(
            "/generar_cupones_gerencia",
            {
                "p_gerente_id": gerente_id,
                "p_cantidad": cantidad,
                "p_porcentaje_descuento": porcentaje_descuento,
            },
        )
        if not isinstance(body, list):
            raise ExternalServiceError(SERVICE, "La API devolvió un lote inválido.", 502)
        return body

    async def asignar_a_medico(self, gerente_id: str, medico_id: str, codigo: str) -> None:
        await self._post(
            "/asignar_cupon_a_medico",
            {"p_gerente_id": gerente_id, "p_medico_id": medico_id, "p_codigo": codigo},
        )

    async def asignar_a_paciente(self, medico_id: str, paciente_id: str, codigo: str) -> None:
        await self._post(
            "/asignar_cupon_a_paciente",
            {"p_medico_id": medico_id, "p_paciente_id": paciente_id, "p_codigo": codigo},
        )

    async def canjear(self, paciente_id: str, codigo: str) -> None:
        await self._post("/canjear_cupon", {"p_paciente_id": paciente_id, "p_codigo": codigo})

    async def listar(
        self,
        *,
        estado: str | None = None,
        medico_id: str | None = None,
        gerente_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Consulta de solo lectura (sirve para conciliar cupones en estado incierto)."""
        if not 1 <= limit <= 100:
            raise ValueError("limit debe estar entre 1 y 100.")
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        for key, value in (("estado", estado), ("medico_id", medico_id), ("gerente_id", gerente_id)):
            if value is not None:
                params[key] = value
        response = await self._send("GET", "/cupones", params=params)
        body = _parse(response)
        if not isinstance(body, dict) or not isinstance(body.get("items"), list):
            raise ExternalServiceError(SERVICE, "La API devolvió un listado inválido.", 502)
        return body

    async def _post(self, path: str, payload: dict[str, Any]) -> Any:
        return _parse(await self._send("POST", path, json=payload))

    async def _send(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url, timeout=self._timeout, transport=self._transport
            ) as client:
                return await client.request(
                    method, path, headers={"X-API-Key": self._api_key}, **kwargs
                )
        except httpx.RequestError as exc:
            raise ExternalServiceError(
                SERVICE, "No se pudo conectar con el servicio de cupones.", 503
            ) from exc


def _parse(response: httpx.Response) -> Any:
    if response.status_code >= 400:
        raise ExternalServiceError(SERVICE, _error_message(response), _error_status(response))
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError as exc:
        raise ExternalServiceError(SERVICE, "La API devolvió JSON inválido.", 502) from exc


def _error_status(response: httpx.Response) -> int:
    # 401/413/415 son errores de configuración o de uso de nuestro lado: se informan como 502.
    return response.status_code if response.status_code in (400, 403, 404, 409, 503) else 502


def _error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        for key in ("message", "mensaje", "error"):
            value = body.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:300]
    return f"El servicio de cupones respondió HTTP {response.status_code}."
