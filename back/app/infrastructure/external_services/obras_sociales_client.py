"""Cliente de la API de obras sociales (Grupo 9). Implementa InsuranceGateway.

Las URLs de simulación (autorizar/rechazar) funcionan como credencial y apuntan al propio
servicio: antes de llamarlas se verifica que tengan el mismo origen que la base configurada.
"""

import uuid
from datetime import date
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.infrastructure.external_services.errors import ExternalServiceError

SERVICE = "Obras sociales"
DEFAULT_BASE_URL = "https://bxsvmfesrtjrqubblgws.supabase.co/functions/v1/api"
PAGE_SIZE = 100
MAX_PAGES = 20
MAX_DEMAND_BYTES = 5 * 1024 * 1024


class ObrasSocialesClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        if not api_key or not api_key.strip():
            raise ValueError("La API key de obras sociales no puede estar vacía.")
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport

    async def listar_obras_sociales(self, buscar: str | None = None) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for page in range(1, MAX_PAGES + 1):
            params: dict[str, Any] = {"por_pagina": PAGE_SIZE, "pagina": page}
            if buscar:
                params["buscar"] = buscar
            body = _object(await self._send("GET", f"{self._base_url}/obras-sociales", params=params))
            data = body.get("datos")
            if not isinstance(data, list):
                raise ExternalServiceError(SERVICE, "La API devolvió un listado inválido.", 502)
            items.extend(item for item in data if isinstance(item, dict))
            total_pages = body.get("total_paginas")
            if not isinstance(total_pages, int) or page >= total_pages:
                break
        return items

    async def obtener_obra_social(self, obra_social_id: str) -> dict[str, Any] | None:
        # La API no expone un GET por id en lo acordado: se busca en el listado completo.
        for item in await self.listar_obras_sociales():
            if item.get("id") == obra_social_id:
                return item
        return None

    async def crear_solicitud(
        self,
        *,
        obra_social_id: str,
        paciente_nombre: str,
        fecha: date,
        referencia_externa: str,
    ) -> dict[str, Any]:
        body = _object(
            await self._send(
                "POST",
                f"{self._base_url}/solicitudes",
                json={
                    "obra_social_id": obra_social_id,
                    "paciente_nombre": paciente_nombre,
                    "fecha": fecha.isoformat(),
                    "referencia_externa": referencia_externa,
                },
            )
        )
        urls = body.get("urls_simulacion")
        if (
            not isinstance(body.get("id"), str)
            or not isinstance(urls, dict)
            or not isinstance(urls.get("autorizar"), str)
            or not isinstance(urls.get("rechazar"), str)
        ):
            raise ExternalServiceError(SERVICE, "La API devolvió una solicitud inválida.", 502)
        return body

    async def autorizar(self, url: str, porcentaje: int | float | None = None) -> dict[str, Any]:
        payload = {"porcentaje": porcentaje} if porcentaje is not None else None
        return _object(await self._send("POST", self._simulation_url(url), json=payload))

    async def rechazar(self, url: str, motivo: str) -> dict[str, Any]:
        return _object(
            await self._send("POST", self._simulation_url(url), json={"motivo": motivo})
        )

    async def presentar_demanda(
        self, solicitud_id: str, filename: str, content: bytes
    ) -> dict[str, Any]:
        if len(content) > MAX_DEMAND_BYTES:
            raise ValueError("El PDF no puede superar los 5 MB.")
        safe_id = str(solicitud_id).strip()
        if not safe_id or "/" in safe_id or "?" in safe_id or "#" in safe_id:
            raise ValueError("Id de solicitud inválido.")
        boundary = uuid.uuid4().hex
        safe_name = filename.replace('"', "").replace("\r", "").replace("\n", "")
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="archivo"; filename="{safe_name}"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
        return _object(
            await self._send(
                "POST",
                f"{self._base_url}/solicitudes/{safe_id}/demanda",
                content=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            )
        )

    def _simulation_url(self, url: str) -> str:
        # Mismo origen (https + host) que la base configurada: evita llamar a terceros.
        base = urlsplit(self._base_url)
        target = urlsplit(url) if isinstance(url, str) else None
        if (
            target is None
            or target.scheme != base.scheme
            or target.netloc != base.netloc
            or target.username
        ):
            raise ExternalServiceError(
                SERVICE, "La URL de simulación no pertenece al servicio configurado.", 502
            )
        return url

    async def _send(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        headers = {"x-api-key": self._api_key, **kwargs.pop("headers", {})}
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport, follow_redirects=False
            ) as client:
                return await client.request(method, url, headers=headers, **kwargs)
        except httpx.RequestError as exc:
            raise ExternalServiceError(
                SERVICE, "No se pudo conectar con el servicio de obras sociales.", 503
            ) from exc


def _object(response: httpx.Response) -> dict[str, Any]:
    if response.status_code >= 400:
        raise ExternalServiceError(SERVICE, _error_message(response), _error_status(response))
    try:
        body = response.json()
    except ValueError as exc:
        raise ExternalServiceError(SERVICE, "La API devolvió JSON inválido.", 502) from exc
    if not isinstance(body, dict):
        raise ExternalServiceError(SERVICE, "La API devolvió una respuesta inválida.", 502)
    return body


def _error_status(response: httpx.Response) -> int:
    return response.status_code if response.status_code in (400, 404, 409, 422, 503) else 502


def _error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            message = error.get("mensaje")
            detail = error.get("detalle")
            if isinstance(message, str) and message.strip():
                if isinstance(detail, str) and detail.strip():
                    return f"{message.strip()} ({detail.strip()})"[:300]
                return message.strip()[:300]
        if isinstance(error, str) and error.strip():
            return error.strip()[:300]
    return f"El servicio de obras sociales respondió HTTP {response.status_code}."
