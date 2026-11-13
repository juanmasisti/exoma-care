"""Cliente de la API de FedEx (módulo 10, de otro grupo). Contrato en la decisión 012."""
from datetime import datetime

import httpx

from app.domain.entities.logistics import TIMEZONE
from app.domain.interfaces.courier import CourierError, PickupStatus

TIMEOUT_SECONDS = 5
# FedEx espera hora argentina sin sufijo de zona: con "Z" o "-03:00" rechaza el pedido.
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
BAD_ANSWER = "FedEx no respondió correctamente."
STATUS_MESSAGES = {401: "FedEx rechazó las credenciales del grupo", 404: "FedEx no encontró el retiro"}


class FedExClient:
    def __init__(self, base_url: str, user: str, password: str, transport: httpx.BaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self.auth = (user, password)
        self.transport = transport  # las pruebas pasan un httpx.MockTransport

    def programar_retiro(self, lugar: str, fecha: datetime) -> str:
        if fecha.utcoffset() is None:
            raise ValueError("La fecha del retiro necesita zona horaria.")
        body = {"lugar": lugar, "fecha_programada": fecha.astimezone(TIMEZONE).strftime(DATE_FORMAT)}
        data = self._call("POST", "/retiros", json=body, auth=self.auth)
        try:
            pickup_id = data["retiro"]["id"]
        except (KeyError, TypeError) as exc:
            raise CourierError(BAD_ANSWER) from exc
        if not isinstance(pickup_id, str):
            raise CourierError(BAD_ANSWER)
        return pickup_id

    def estado_retiro(self, uuid: str) -> PickupStatus:
        data = self._call("GET", f"/retiros/{uuid}")  # público: sin credenciales
        try:
            estado = data["estado"]
        except (KeyError, TypeError) as exc:
            raise CourierError(BAD_ANSWER) from exc
        try:
            return PickupStatus(estado)
        except ValueError as exc:
            raise CourierError(f"FedEx devolvió un estado de retiro desconocido: {estado}.") from exc

    def _call(self, method: str, path: str, **kwargs):
        try:
            with httpx.Client(timeout=TIMEOUT_SECONDS, transport=self.transport) as http:
                response = http.request(method, self.base_url + path, **kwargs)
        except httpx.TimeoutException as exc:
            raise CourierError("FedEx tardó demasiado en responder.") from exc
        except httpx.HTTPError as exc:
            raise CourierError("No se pudo conectar con FedEx.") from exc
        if response.is_error:
            raise CourierError(_error_message(response))
        try:
            return response.json()
        except ValueError as exc:
            raise CourierError(BAD_ANSWER) from exc


def _error_message(response: httpx.Response) -> str:
    default = "FedEx tuvo un error interno" if response.is_server_error else "FedEx rechazó el pedido"
    message = STATUS_MESSAGES.get(response.status_code, default)
    try:
        detail = response.json().get("error")
    except (ValueError, AttributeError):
        detail = None
    return f"{message}: {detail}" if isinstance(detail, str) and detail else f"{message}."
