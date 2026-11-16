import asyncio
import json
import logging
from typing import Any
from uuid import UUID

import httpx
from pydantic import ValidationError

from app.domain.dtos.notification_dto import (
    NotificacionInput,
    NotificacionResultado,
)
from app.domain.interfaces.notification_service import INotificationService
from app.infrastructure.external_services.errors import ExternalServiceError

NOTIFICATION_BASE_URL = "https://jpnbycihugrzeeolobev.supabase.co/functions/v1"
MAX_PAYLOAD_BYTES = 64 * 1024
logger = logging.getLogger(__name__)


class IdempotencyConflictError(ExternalServiceError):
    def __init__(self, message: str):
        super().__init__("Notificaciones", message, 409)


class TTPSNotificationClient(INotificationService):
    def __init__(
        self,
        api_key: str,
        base_url: str = NOTIFICATION_BASE_URL,
        timeout: float = 10.0,
        retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        if not api_key:
            raise ValueError("La API key de notificaciones no puede estar vacía.")
        if retries < 0:
            raise ValueError("La cantidad de reintentos no puede ser negativa.")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._retries = retries
        self._transport = transport

    async def enviar_aviso(
        self, datos: NotificacionInput
    ) -> NotificacionResultado:
        payload: dict[str, Any] = {
            "asunto": datos.asunto,
            "mensaje": datos.mensaje,
            "referencia": datos.referencia,
            "destinatarios": [
                {"canal": "email", "destino": email}
                for email in datos.destinatarios
            ],
        }
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        if len(body) > MAX_PAYLOAD_BYTES:
            raise ValueError("El cuerpo de la notificación supera los 64 KB.")

        response = await self._request(
            "POST",
            "/avisos",
            headers={"Idempotency-Key": datos.idempotency_key},
            content=body,
            retry_transient_failures=True,
        )
        if response.status_code == 409:
            raise IdempotencyConflictError(_response_error(response))
        if response.status_code not in (200, 202):
            raise ExternalServiceError(
                "Notificaciones",
                _response_error(response),
                response.status_code if response.status_code >= 400 else 502,
            )

        try:
            response_body = response.json()
            if not isinstance(response_body, dict):
                raise ValueError("La respuesta no es un objeto JSON.")
            resultado = NotificacionResultado(
                aviso_id=response_body["id"],
                estado=response_body["estado"],
                creado=response_body["creado"],
            )
            if resultado.creado != (response.status_code == 202):
                raise ValueError("El estado HTTP y el campo creado no coinciden.")
            return resultado
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise ExternalServiceError(
                "Notificaciones",
                "El servicio devolvió una respuesta de aviso inválida.",
                502,
            ) from exc

    async def verificar_conexion(self) -> dict[str, Any]:
        return _json_object(await self._request("GET", "/avisos"))

    async def consultar_estado(self, aviso_id: str) -> dict[str, Any]:
        try:
            normalized_id = str(UUID(aviso_id))
        except ValueError as exc:
            raise ValueError("aviso_id debe ser un UUID válido.") from exc
        return _json_object(
            await self._request("GET", f"/avisos/{normalized_id}")
        )

    async def listar_pendientes(self, limite: int = 25) -> dict[str, Any]:
        if not 1 <= limite <= 100:
            raise ValueError("limite debe estar entre 1 y 100.")
        return _json_object(
            await self._request("GET", "/avisos/pendientes", params={"limite": limite})
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
        params: dict[str, int] | None = None,
        retry_transient_failures: bool = False,
    ) -> httpx.Response:
        request_headers = {"X-API-Key": self._api_key}
        request_headers.update(headers or {})
        if content is not None:
            request_headers["Content-Type"] = "application/json"

        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            for attempt in range(self._retries + 1):
                try:
                    response = await client.request(
                        method,
                        path,
                        headers=request_headers,
                        content=content,
                        params=params,
                    )
                except httpx.RequestError as exc:
                    if retry_transient_failures and attempt < self._retries:
                        await asyncio.sleep(0.1 * (attempt + 1))
                        continue
                    raise ExternalServiceError(
                        "Notificaciones",
                        "No se pudo conectar con el servicio de avisos.",
                        503,
                    ) from exc

                if (
                    retry_transient_failures
                    and response.status_code >= 500
                    and attempt < self._retries
                ):
                    await asyncio.sleep(0.1 * (attempt + 1))
                    continue
                return response

        raise RuntimeError("Se agotaron los intentos de notificación.")


class NotificationClient(TTPSNotificationClient):
    """Alias compatible para los usos existentes del cliente."""

    async def enviar_aviso_resultado(
        self,
        study_id: int,
        asunto: str,
        mensaje: str,
        destinatarios: list[dict[str, str]],
    ) -> int:
        resultado = await self.enviar_aviso(
            NotificacionInput(
                asunto=asunto,
                mensaje=mensaje,
                destinatarios=[destinatario["destino"] for destinatario in destinatarios],
                idempotency_key=f"resultado-{study_id}-aviso",
                referencia=str(study_id),
            )
        )
        if resultado.creado:
            logger.info("Result notification accepted for study %s", study_id)
            return 202
        logger.info("Result notification already existed for study %s", study_id)
        return 200


def _json_object(response: httpx.Response) -> dict[str, Any]:
    if response.status_code != 200:
        raise ExternalServiceError(
            "Notificaciones",
            _response_error(response),
            response.status_code if response.status_code >= 400 else 502,
        )
    try:
        body = response.json()
    except ValueError as exc:
        raise ExternalServiceError(
            "Notificaciones", "El servicio devolvió JSON inválido.", 502
        ) from exc
    if not isinstance(body, dict):
        raise ExternalServiceError(
            "Notificaciones", "El servicio devolvió una respuesta inválida.", 502
        )
    return body


def _response_error(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, str):
            return error
        legacy_message = body.get("message")
        if isinstance(legacy_message, str):
            return legacy_message
    text = response.text.strip()
    return text[:500] if text else f"El servicio de avisos respondió HTTP {response.status_code}."
