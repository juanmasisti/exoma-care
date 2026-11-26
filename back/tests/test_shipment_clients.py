"""Clientes del envío (T06a): adaptador de FedEx y Ministerio simulado. La API del envío está en test_shipments_api.py."""
import base64
import json
from datetime import UTC, datetime

import httpx
import pytest

from app.domain.entities.logistics import TIMEZONE
from app.domain.interfaces.courier import CourierError, PickupStatus
from app.infrastructure.adapters.fedex_client import FedExClient
from app.infrastructure.adapters.simulated_health_ministry import SimulatedHealthMinistry

NOW = datetime(2026, 12, 1, 12, 0, tzinfo=TIMEZONE)
PICKUP_ID = "3f2b8c1e-6d4a-4f7e-9a10-2b5c7d8e9f01"


# Adaptador HTTP con un transporte falso de httpx: no sale a internet.

BASE_URL = "https://fedex.test/functions/v1/fedex"


def fedex_with(handler):
    return FedExClient(BASE_URL, "grupo-demo", "clave-secreta-demo", transport=httpx.MockTransport(handler))


def test_client_sends_argentine_time_without_zone():
    seen = {}

    def handler(request):
        seen["request"] = request
        return httpx.Response(201, json={"mensaje": "ok", "retiro": {"id": PICKUP_ID}})
    pickup_id = fedex_with(handler).programar_retiro("Laboratorio DEMO", datetime(2026, 12, 15, 18, tzinfo=UTC))
    request = seen["request"]
    assert pickup_id == PICKUP_ID
    assert request.method == "POST" and str(request.url) == f"{BASE_URL}/retiros"
    assert json.loads(request.content) == {"lugar": "Laboratorio DEMO", "fecha_programada": "2026-12-15T15:00:00"}
    credentials = base64.b64encode(b"grupo-demo:clave-secreta-demo").decode()
    assert request.headers["Authorization"] == f"Basic {credentials}"


@pytest.mark.parametrize("estado", ["PROGRAMADO", "RETIRADO"])
def test_client_reads_pickup_status(estado):
    seen = {}

    def handler(request):
        seen["request"] = request
        return httpx.Response(200, json={"id": PICKUP_ID, "estado": estado})
    assert fedex_with(handler).estado_retiro(PICKUP_ID) == PickupStatus(estado)
    assert str(seen["request"].url) == f"{BASE_URL}/retiros/{PICKUP_ID}"
    assert "Authorization" not in seen["request"].headers  # la consulta es pública


def test_client_rejects_unknown_status():
    def handler(request):
        return httpx.Response(200, json={"id": PICKUP_ID, "estado": "PERDIDO"})
    with pytest.raises(CourierError, match="desconocido: PERDIDO"):
        fedex_with(handler).estado_retiro(PICKUP_ID)


@pytest.mark.parametrize(("response", "message"), [
    (httpx.Response(400, json={"error": "La fecha debe ser futura"}), "FedEx rechazó el pedido: La fecha debe ser futura"),
    (httpx.Response(401, json={"error": "Credenciales inválidas"}), "credenciales del grupo"),
    (httpx.Response(404, json={"error": "Retiro no encontrado"}), "no encontró el retiro"),
    (httpx.Response(500, text="falla"), "FedEx tuvo un error interno."),
    (httpx.Response(201, text="no es json"), "no respondió correctamente"),
    (httpx.Response(201, json={"retiro": {}}), "no respondió correctamente"),
])
def test_client_translates_errors(response, message):
    with pytest.raises(CourierError, match=message) as error:
        fedex_with(lambda request: response).programar_retiro("Laboratorio DEMO", NOW)
    assert "clave-secreta-demo" not in str(error.value)


def test_client_translates_timeout():
    def handler(request):
        raise httpx.ReadTimeout("lento", request=request)
    with pytest.raises(CourierError, match="tardó demasiado"):
        fedex_with(handler).estado_retiro(PICKUP_ID)


def test_client_translates_connection_error():
    def handler(request):
        raise httpx.ConnectError("sin red", request=request)
    with pytest.raises(CourierError, match="No se pudo conectar con FedEx"):
        fedex_with(handler).estado_retiro(PICKUP_ID)


def test_client_rejects_date_without_zone():
    with pytest.raises(ValueError, match="zona horaria"):
        fedex_with(lambda request: httpx.Response(201)).programar_retiro("Laboratorio DEMO", datetime(2026, 12, 15, 15))


def test_simulated_ministry_authorizes_with_a_pdf():
    authorization = SimulatedHealthMinistry().solicitar_autorizacion("dni,nombre\n30111222,Paciente DEMO Núñez\n")
    assert authorization.status == "autorizado"
    assert authorization.pdf.startswith(b"%PDF")
