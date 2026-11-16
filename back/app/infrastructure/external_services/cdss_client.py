from typing import Any

import httpx

from app.infrastructure.external_services.errors import ExternalServiceError

CDSS_UNAVAILABLE_MESSAGE = "El catálogo de patologías CDSS no está disponible"


class CDSSClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://genexoma.onrender.com/api/v1",
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        if not api_key.strip():
            raise ValueError("La clave de API de CDSS no puede estar vacía.")
        if not base_url.strip():
            raise ValueError("base_url de CDSS no puede estar vacía.")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport

    async def obtener_patologias(self) -> list[dict[str, str]]:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                headers={"X-API-Key": self._api_key, "Accept": "application/json"},
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                response = await client.get("patologias")
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            raise ExternalServiceError(
                "CDSS", CDSS_UNAVAILABLE_MESSAGE, 503
            ) from exc

        if response.status_code == 401:
            raise ExternalServiceError(
                "CDSS", "Credenciales inválidas para el catálogo CDSS.", 401
            )
        if response.status_code in {500, 503}:
            raise ExternalServiceError("CDSS", CDSS_UNAVAILABLE_MESSAGE, 503)
        if response.status_code >= 400:
            raise ExternalServiceError(
                "CDSS",
                _response_message(response),
                response.status_code,
            )

        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise ExternalServiceError(
                "CDSS", CDSS_UNAVAILABLE_MESSAGE, 503
            ) from exc
        if not isinstance(payload, list):
            raise ExternalServiceError("CDSS", CDSS_UNAVAILABLE_MESSAGE, 503)

        pathologies = []
        for item in payload:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("codigo"), str)
                or not isinstance(item.get("nombre"), str)
                or not item["codigo"].strip()
                or not item["nombre"].strip()
            ):
                raise ExternalServiceError("CDSS", CDSS_UNAVAILABLE_MESSAGE, 503)
            pathologies.append(
                {"codigo": item["codigo"], "nombre": item["nombre"]}
            )
        return pathologies


def _response_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict) and isinstance(body.get("message"), str):
        return body["message"]
    text = response.text.strip()
    return text[:500] if text else f"CDSS respondió HTTP {response.status_code}."
