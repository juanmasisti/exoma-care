import base64
import json
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.api.dependencies import get_database_session
from app.api.routes.extraction_centers import get_clock
from app.api.routes.shipments import get_courier
from app.config import get_settings
from app.domain.entities.logistics import TIMEZONE
from app.domain.interfaces.courier import CourierError, PickupStatus
from app.infrastructure.adapters.fedex_client import FedExClient
from app.infrastructure.adapters.simulated_health_ministry import SimulatedHealthMinistry
from app.infrastructure.database.models import Usuario
from app.infrastructure.database.security import hash_password
from app.infrastructure.database.session import Base
from app.main import app

TEST_HASH = hash_password("shipment-test-password")
NOW = datetime(2026, 12, 1, 12, 0, tzinfo=TIMEZONE)
PICKUP_ID = "3f2b8c1e-6d4a-4f7e-9a10-2b5c7d8e9f01"


class FakeCourier:
    """Doble del Protocol Courier: anota cada llamada y, si `error` está cargado, lo lanza."""

    def __init__(self):
        self.calls = []
        self.error = None

    def programar_retiro(self, lugar, fecha):
        self.calls.append((lugar, fecha))
        if self.error:
            raise self.error
        return PICKUP_ID

    def estado_retiro(self, uuid):
        self.calls.append(uuid)
        if self.error:
            raise self.error
        return PickupStatus.RETIRADO


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "shipment-test-secret-at-least-32-bytes-long")
    engine = create_engine(f"sqlite:///{tmp_path / 'shipments.db'}", connect_args={"check_same_thread": False})
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for identifier, role in enumerate(["lab_administrator", "patient"], 1):
            session.add(Usuario(id=identifier, username=f"demo{identifier}", role=role, first_name="Demo",
                                last_name="Prueba", phone="000", email=f"demo{identifier}@example.test",
                                password_hash=TEST_HASH))
        session.commit()
    courier = FakeCourier()

    def database_session():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_database_session] = database_session
    app.dependency_overrides[get_courier] = lambda: courier
    app.dependency_overrides[get_clock] = lambda: NOW
    try:
        with TestClient(app) as http:
            yield http, courier
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def login(http, identifier=1):
    result = http.post("/api/auth/login", json={"email": f"demo{identifier}@example.test",
                                                "password": "shipment-test-password"})
    assert result.status_code == 200
    return {"Authorization": "Bearer " + result.json()["access_token"]}


def schedule(http, scheduled_at, identifier=1):
    return http.post("/api/shipments/pickups", json={"scheduled_at": scheduled_at}, headers=login(http, identifier))


def test_schedule_pickup_sends_lab_address_and_aware_date(client):
    http, courier = client
    response = schedule(http, "2026-12-15T18:00:00Z")
    assert response.status_code == 201
    assert response.json() == {"pickup_id": PICKUP_ID}
    ((lugar, fecha),) = courier.calls
    assert lugar == get_settings().central_lab_address
    assert fecha == datetime(2026, 12, 15, 18, tzinfo=UTC)


def test_pickup_status_comes_from_the_courier(client):
    http, courier = client
    response = http.get(f"/api/shipments/pickups/{PICKUP_ID}", headers=login(http))
    assert response.status_code == 200
    assert response.json() == {"pickup_id": PICKUP_ID, "status": "RETIRADO"}
    assert courier.calls == [PICKUP_ID]


def test_courier_error_is_a_readable_502(client):
    http, courier = client
    courier.error = CourierError("FedEx tardó demasiado en responder.")
    response = schedule(http, "2026-12-15T15:00:00-03:00")
    assert response.status_code == 502
    assert response.json()["detail"] == "FedEx tardó demasiado en responder."
    response = http.get(f"/api/shipments/pickups/{PICKUP_ID}", headers=login(http))
    assert response.status_code == 502


@pytest.mark.parametrize("scheduled_at", ["2026-12-01T09:00:00-03:00", "2026-12-01T12:00:00-03:00"])
def test_past_or_now_date_is_422_without_calling_fedex(client, scheduled_at):
    http, courier = client
    response = schedule(http, scheduled_at)
    assert response.status_code == 422
    assert response.json()["detail"] == "La fecha del retiro tiene que ser futura."
    assert courier.calls == []


def test_validation_errors(client):
    http, courier = client
    assert schedule(http, "2026-12-15T15:00:00").status_code == 422  # sin zona horaria
    assert http.get("/api/shipments/pickups/no-es-un-uuid", headers=login(http)).status_code == 422
    assert courier.calls == []


def test_permissions(client):
    http, _courier = client
    assert http.post("/api/shipments/pickups", json={"scheduled_at": "2026-12-15T18:00:00Z"}).status_code == 401
    assert http.get(f"/api/shipments/pickups/{PICKUP_ID}").status_code == 401
    assert schedule(http, "2026-12-15T18:00:00Z", identifier=2).status_code == 403
    assert http.get(f"/api/shipments/pickups/{PICKUP_ID}", headers=login(http, 2)).status_code == 403


def test_missing_fedex_configuration_is_a_502(client, monkeypatch):
    http, _courier = client
    del app.dependency_overrides[get_courier]
    monkeypatch.setenv("FEDEX_URL", "")
    response = schedule(http, "2026-12-15T18:00:00Z")
    assert response.status_code == 502
    assert response.json()["detail"] == "FedEx no está configurado."


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
