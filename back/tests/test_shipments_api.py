"""Envío del lote (T06): CSV, autorización del Ministerio (simulado) y retiro de FedEx (doble de prueba)."""
import csv
import io
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from app.api.dependencies import get_database_session
from app.api.routes.extraction_centers import get_clock
from app.api.routes.shipments import get_courier, get_health_ministry, get_shipment_service
from app.config import get_settings
from app.domain.entities.logistics import TIMEZONE
from app.domain.interfaces.courier import CourierError, PickupStatus
from app.infrastructure.adapters.simulated_health_ministry import SimulatedHealthMinistry
from app.infrastructure.database.models import Usuario
from app.infrastructure.database.security import hash_password
from app.infrastructure.database.session import Base
from app.infrastructure.repositories.sqlalchemy_shipment_repository import SQLAlchemyShipmentRepository
from app.main import app

TEST_HASH = hash_password("shipment-test-password")
NOW = datetime(2026, 12, 1, 12, 0, tzinfo=TIMEZONE)  # martes
PICKUP_ID = "3f2b8c1e-6d4a-4f7e-9a10-2b5c7d8e9f01"
VALID_PICKUP = "2026-12-02T10:00:00-03:00"  # miércoles hábil
CLOSED_SET, ASSEMBLING_SET = 1, 2
# Muestra -> (lote, paciente). La 5 está recibida y sin lote.
SAMPLES = {1: (CLOSED_SET, 1), 2: (CLOSED_SET, 2), 3: (CLOSED_SET, 1), 4: (ASSEMBLING_SET, 2), 5: (None, 1)}
PATIENTS = {1: ("45000001", "Gómez", "Ana"), 2: ("45000002", "Pérez", "Luis")}


class FakeCourier:
    def __init__(self):
        self.calls = []
        self.error = None
        self.status = PickupStatus.PROGRAMADO

    def programar_retiro(self, lugar, fecha):
        self.calls.append((lugar, fecha))
        if self.error:
            raise self.error
        return PICKUP_ID

    def estado_retiro(self, uuid):
        self.calls.append(uuid)
        if self.error:
            raise self.error
        return self.status


class FailingMinistry:
    def solicitar_autorizacion(self, csv):
        raise ConnectionError("sin conexión")


def _insert_data(connection):
    connection.execute(text("INSERT INTO holidays (day, description) VALUES ('2026-12-08', 'Inmaculada Concepción de María')"))
    connection.execute(text("INSERT INTO provinces (id, name) VALUES (1, 'DEMO')"))
    connection.execute(text("""INSERT INTO extraction_centers (id, name, address, city, province_id, latitude, longitude, active)
        VALUES (1, 'Centro DEMO 1', 'Calle DEMO 1', 'DEMO', 1, 0, 0, 1)"""))
    for patient_id, (dni, last_name, first_name) in PATIENTS.items():
        connection.execute(text("INSERT INTO patients (id, dni, nombre, apellido, version) VALUES (:id, :dni, :first, :last, 1)"),
                           {"id": patient_id, "dni": dni, "first": first_name, "last": last_name})
    for sample_set_id, status in ((CLOSED_SET, "closed"), (ASSEMBLING_SET, "assembling")):
        connection.execute(text("INSERT INTO sample_sets (id, status, is_urgent, created_at, closed_at, version) "
                                "VALUES (:id, :status, 0, '2026-11-30 12:00:00', NULL, 1)"),
                           {"id": sample_set_id, "status": status})
    slots = {}
    for sample_id, (sample_set_id, patient_id) in SAMPLES.items():
        params = {"id": sample_id, "patient": patient_id,
                  "status": "in_sample_set" if sample_set_id else "received"}
        connection.execute(text("INSERT INTO studies (id, patient_id, status, created_at) "
                                "VALUES (:id, :patient, 'listo_para_retirar', '2026-11-01')"), params)
        connection.execute(text("""INSERT INTO appointments (id, study_id, center_id, starts_at, status, study_status_before, created_at)
            VALUES (:id, :id, 1, '2026-11-02 13:00:00', 'attended', 'pagado', '2026-11-01 13:00:00')"""), params)
        connection.execute(text("INSERT INTO extraction_notices (id, external_id, payload, received_at) "
                                "VALUES (:id, 'aviso-' || :id, '{}', '2026-11-02')"), params)
        connection.execute(text("""INSERT INTO samples (id, study_id, appointment_id, extraction_notice_id, volume_ml, status, is_current)
            VALUES (:id, :id, :id, :id, 3, :status, 1)"""), params)
        if sample_set_id:
            slots[sample_set_id] = slots.get(sample_set_id, 0) + 1
            connection.execute(text("INSERT INTO sample_set_items (sample_set_id, sample_id, slot) VALUES (:set, :id, :slot)"),
                               {"set": sample_set_id, "id": sample_id, "slot": slots[sample_set_id]})


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "shipment-test-secret-at-least-32-bytes-long")
    # Nunca la carpeta real ni el repo.
    monkeypatch.setenv("SHIPMENT_FILES_DIR", str(tmp_path / "archivos"))
    engine = create_engine(f"sqlite:///{tmp_path / 'shipments.db'}", connect_args={"check_same_thread": False})
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for identifier, role in enumerate(["lab_administrator", "patient"], 1):
            session.add(Usuario(id=identifier, username=f"demo{identifier}", role=role, first_name="Demo",
                                last_name="Prueba", phone="000", email=f"demo{identifier}@example.test",
                                password_hash=TEST_HASH))
        session.commit()
    with engine.begin() as connection:
        _insert_data(connection)
    courier = FakeCourier()

    def database_session():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_database_session] = database_session
    app.dependency_overrides[get_courier] = lambda: courier
    app.dependency_overrides[get_clock] = lambda: NOW
    try:
        with TestClient(app) as http:
            yield http, courier, engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def login(http, identifier=1):
    result = http.post("/api/auth/login", json={"email": f"demo{identifier}@example.test",
                                                "password": "shipment-test-password"})
    assert result.status_code == 200
    return {"Authorization": "Bearer " + result.json()["access_token"]}


def close_set(engine, ministry=None):
    """Lo que hace el armado de lotes (T05): el enganche en la sesión del pedido, y el commit afuera."""
    with Session(engine) as session:
        get_shipment_service(session, ministry or SimulatedHealthMinistry()).al_cerrar_lote(CLOSED_SET, NOW)
        session.commit()


def schedule(http, scheduled_at=VALID_PICKUP, sample_set_id=CLOSED_SET):
    return http.post(f"/api/shipments/{sample_set_id}/pickup", json={"scheduled_at": scheduled_at}, headers=login(http))


def refresh(http, sample_set_id=CLOSED_SET):
    return http.post(f"/api/shipments/{sample_set_id}/refresh", headers=login(http))


def rows(engine, query):
    with engine.connect() as connection:
        return connection.execute(text(query)).all()


def test_closing_a_set_writes_a_csv_with_exactly_its_samples_and_the_authorization(setup):
    http, _courier, _engine = setup
    close_set(_engine)
    response = http.get(f"/api/shipments/{CLOSED_SET}", headers=login(http))
    assert response.json() == {"id": CLOSED_SET, "status": "closed", "has_csv": True, "has_authorization": True,
                               "pickup_at": None, "courier_pickup_id": None}
    downloaded = http.get(f"/api/shipments/{CLOSED_SET}/csv", headers=login(http))
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"].startswith("text/csv")
    assert list(csv.reader(io.StringIO(downloaded.text))) == [
        ["dni", "apellido", "nombre", "codigo_estudio", "id_muestra"],
        ["45000001", "Gómez", "Ana", "EST-000001", "1"],
        ["45000002", "Pérez", "Luis", "EST-000002", "2"],
        ["45000001", "Gómez", "Ana", "EST-000003", "3"],
    ]
    assert "corea" not in downloaded.text.lower()
    pdf = http.get(f"/api/shipments/{CLOSED_SET}/authorization.pdf", headers=login(http))
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    # Los archivos quedan en la carpeta configurada; en el lote, solo su nombre.
    files_dir = get_settings().shipment_files_dir
    assert sorted(path.name for path in files_dir.iterdir()) == ["lote-1-autorizacion.pdf", "lote-1.csv"]
    assert rows(_engine, "SELECT csv_path, authorization_pdf_path FROM sample_sets WHERE id = 1") == [
        ("lote-1.csv", "lote-1-autorizacion.pdf")]


def test_a_ministry_failure_on_close_does_not_raise_and_the_retry_authorizes_once(setup):
    http, _courier, engine = setup
    close_set(engine, FailingMinistry())  # no lanza: la llegada sigue
    assert http.get(f"/api/shipments/{CLOSED_SET}", headers=login(http)).json()["has_authorization"] is False
    assert http.get(f"/api/shipments/{CLOSED_SET}/authorization.pdf", headers=login(http)).status_code == 404

    app.dependency_overrides[get_health_ministry] = FailingMinistry
    failed = http.post(f"/api/shipments/{CLOSED_SET}/authorization", headers=login(http))
    assert failed.status_code == 502
    assert failed.json()["detail"] == "El Ministerio de Salud no respondió. Reintentá la autorización."
    del app.dependency_overrides[get_health_ministry]

    retried = http.post(f"/api/shipments/{CLOSED_SET}/authorization", headers=login(http))
    assert retried.status_code == 200 and retried.json()["has_authorization"] is True
    again = http.post(f"/api/shipments/{CLOSED_SET}/authorization", headers=login(http))
    assert again.status_code == 409
    assert again.json()["detail"] == "El lote ya tiene la autorización del Ministerio de Salud."


def test_an_assembling_set_cannot_be_authorized_or_scheduled(setup):
    http, courier, _engine = setup
    assert http.post(f"/api/shipments/{ASSEMBLING_SET}/authorization", headers=login(http)).status_code == 409
    assert schedule(http, sample_set_id=ASSEMBLING_SET).status_code == 409
    assert courier.calls == []


def test_scheduling_without_authorization_is_409_without_calling_fedex(setup):
    http, courier, _engine = setup
    response = schedule(http)
    assert response.status_code == 409
    assert response.json()["detail"] == "Falta la autorización del Ministerio de Salud."
    assert courier.calls == []


@pytest.mark.parametrize(("scheduled_at", "detail"), [
    ("2026-12-02T08:59:00-03:00", "FedEx retira en días hábiles, de 9 a 18 h."),
    ("2026-12-02T18:00:00-03:00", "FedEx retira en días hábiles, de 9 a 18 h."),
    ("2026-12-05T10:00:00-03:00", "FedEx retira en días hábiles, de 9 a 18 h."),  # sábado
    ("2026-12-08T10:00:00-03:00", "FedEx retira en días hábiles, de 9 a 18 h."),  # feriado de la tabla
    ("2026-12-01T12:00:00-03:00", "La fecha del retiro tiene que ser futura."),
])
def test_scheduling_out_of_hours_on_a_holiday_or_in_the_past_is_422(setup, scheduled_at, detail):
    http, courier, engine = setup
    close_set(engine)
    response = schedule(http, scheduled_at)
    assert response.status_code == 422
    assert response.json()["detail"] == detail
    assert courier.calls == []


def test_scheduling_a_pickup_calls_fedex_at_the_central_lab_and_waits(setup):
    http, courier, engine = setup
    close_set(engine)
    response = schedule(http)
    assert response.status_code == 200
    assert response.json() | {"pickup_at": None} == {"id": CLOSED_SET, "status": "awaiting_pickup", "has_csv": True,
                                                     "has_authorization": True, "pickup_at": None,
                                                     "courier_pickup_id": PICKUP_ID}
    assert datetime.fromisoformat(response.json()["pickup_at"]) == datetime.fromisoformat(VALID_PICKUP)
    assert courier.calls == [(get_settings().central_lab_address, datetime.fromisoformat(VALID_PICKUP))]
    again = schedule(http)
    assert again.status_code == 409 and again.json()["detail"] == "El lote ya tiene un retiro programado."


def test_when_fedex_is_down_the_error_is_clear_and_the_set_does_not_change(setup):
    http, courier, engine = setup
    close_set(engine)
    courier.error = CourierError("FedEx tardó demasiado en responder.")
    response = schedule(http)
    assert response.status_code == 502
    assert response.json()["detail"] == "FedEx tardó demasiado en responder."
    assert rows(engine, "SELECT status, courier_pickup_id, pickup_at FROM sample_sets WHERE id = 1") == [
        ("closed", None, None)]

    courier.error = None
    schedule(http)
    courier.error = CourierError("FedEx no responde.")
    assert refresh(http).status_code == 502
    assert rows(engine, "SELECT status FROM sample_sets WHERE id = 1") == [("awaiting_pickup",)]


def test_before_the_pickup_the_refresh_keeps_the_set_awaiting(setup):
    http, courier, engine = setup
    close_set(engine)
    schedule(http)
    response = refresh(http)
    assert response.status_code == 200 and response.json()["status"] == "awaiting_pickup"
    assert courier.calls[-1] == PICKUP_ID
    assert rows(engine, "SELECT DISTINCT status FROM samples WHERE id IN (1, 2, 3)") == [("in_sample_set",)]


def test_refreshing_twice_a_done_pickup_makes_a_single_transition(setup):
    http, courier, engine = setup
    close_set(engine)
    schedule(http)
    courier.status = PickupStatus.RETIRADO
    first = refresh(http)
    assert first.status_code == 200 and first.json()["status"] == "in_transit_to_sequencing_lab"
    calls = len(courier.calls)
    second = refresh(http)
    assert second.status_code == 200 and second.json()["status"] == "in_transit_to_sequencing_lab"
    assert len(courier.calls) == calls  # ya en viaje: ni siquiera consulta a FedEx

    assert rows(engine, "SELECT id, status FROM samples ORDER BY id") == [
        (1, "in_transit_to_sequencing_lab"), (2, "in_transit_to_sequencing_lab"), (3, "in_transit_to_sequencing_lab"),
        (4, "in_sample_set"), (5, "received")]
    assert rows(engine, "SELECT sample_id, actor_id FROM sample_events WHERE to_status = 'in_transit_to_sequencing_lab' "
                        "ORDER BY sample_id") == [(1, 1), (2, 1), (3, 1)]
    assert rows(engine, "SELECT id FROM studies WHERE status = 'en_viaje_a_corea' ORDER BY id") == [(1,), (2,), (3,)]


def test_each_set_change_applies_once_even_if_the_set_was_read_before(setup):
    _http, _courier, engine = setup
    with Session(engine) as session:
        shipments = SQLAlchemyShipmentRepository(session)
        assert shipments.save_authorization(CLOSED_SET, "lote-1.csv", "lote-1-autorizacion.pdf")
        assert not shipments.save_authorization(CLOSED_SET, "otro.csv", "otro.pdf")
        assert shipments.schedule_pickup(CLOSED_SET, PICKUP_ID, NOW)
        assert not shipments.schedule_pickup(CLOSED_SET, PICKUP_ID, NOW)
        assert shipments.mark_in_transit(CLOSED_SET)
        assert not shipments.mark_in_transit(CLOSED_SET)
        assert not shipments.schedule_pickup(ASSEMBLING_SET, PICKUP_ID, NOW)
        session.commit()
    assert rows(engine, "SELECT status, csv_path, version FROM sample_sets WHERE id = 1") == [
        ("in_transit_to_sequencing_lab", "lote-1.csv", 4)]


def test_a_late_request_does_not_move_samples_again(setup):
    http, courier, engine = setup
    close_set(engine)
    schedule(http)
    courier.status = PickupStatus.RETIRADO
    refresh(http)
    # Un pedido que leyó el lote esperando el retiro llega tarde a moverlo: mark_in_transit da False.
    with Session(engine) as session:
        get_shipment_service(session, SimulatedHealthMinistry())._depart(CLOSED_SET, NOW, 1)
        session.commit()
    assert rows(engine, "SELECT COUNT(*) FROM sample_events WHERE to_status = 'in_transit_to_sequencing_lab'") == [(3,)]


def test_the_close_hook_does_not_commit(setup):
    _http, _courier, engine = setup
    with Session(engine) as session:
        get_shipment_service(session, SimulatedHealthMinistry()).al_cerrar_lote(CLOSED_SET, NOW)
        session.rollback()  # quien atiende el pedido lo deshace
    assert rows(engine, "SELECT csv_path, authorization_pdf_path FROM sample_sets WHERE id = 1") == [(None, None)]


def test_the_close_hook_does_not_raise_if_the_set_is_not_closed(setup):
    _http, _courier, engine = setup
    with Session(engine) as session:
        get_shipment_service(session, SimulatedHealthMinistry()).al_cerrar_lote(ASSEMBLING_SET, NOW)


def test_refresh_without_a_pickup_and_missing_sets(setup):
    http, _courier, _engine = setup
    response = refresh(http)
    assert response.status_code == 409 and response.json()["detail"] == "El lote no tiene un retiro programado."
    for method, path in [("get", "/api/shipments/99"), ("post", "/api/shipments/99/authorization"),
                         ("get", "/api/shipments/99/csv"), ("get", "/api/shipments/99/authorization.pdf"),
                         ("post", "/api/shipments/99/refresh")]:
        missing = getattr(http, method)(path, headers=login(http))
        assert missing.status_code == 404 and missing.json()["detail"] == "El lote no existe."
    assert schedule(http, sample_set_id=99).status_code == 404


def test_validation_errors(setup):
    http, courier, engine = setup
    close_set(engine)
    assert schedule(http, "2026-12-02T10:00:00").status_code == 422  # sin zona horaria
    assert http.post(f"/api/shipments/{CLOSED_SET}/pickup", json={}, headers=login(http)).status_code == 422
    assert courier.calls == []


ENDPOINTS = [("get", "/api/shipments/1"), ("post", "/api/shipments/1/authorization"), ("get", "/api/shipments/1/csv"),
             ("get", "/api/shipments/1/authorization.pdf"), ("post", "/api/shipments/1/pickup"),
             ("post", "/api/shipments/1/refresh")]


def test_only_the_lab_administrator_uses_the_shipment(setup):
    http, _courier, _engine = setup
    for method, path in ENDPOINTS:
        assert getattr(http, method)(path).status_code == 401
        assert getattr(http, method)(path, headers=login(http, 2)).status_code == 403


def test_missing_fedex_configuration_is_a_502(setup, monkeypatch):
    http, _courier, engine = setup
    close_set(engine)
    del app.dependency_overrides[get_courier]
    monkeypatch.setenv("FEDEX_URL", "")
    response = schedule(http)
    assert response.status_code == 502
    assert response.json()["detail"] == "FedEx no está configurado."
