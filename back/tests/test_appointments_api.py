from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_database_session
from app.api.routes.extraction_centers import get_clock
from app.domain.entities.logistics import TIMEZONE
from app.infrastructure.database.logistics_models import AppointmentModel, ExtractionCenterModel
from app.infrastructure.database.models import Paciente, Usuario
from app.infrastructure.database.security import hash_password
from app.infrastructure.database.seed_demo_extraction_centers import seed_demo_extraction_centers
from app.infrastructure.database.session import Base
from app.infrastructure.database.study_models import StudyModel
from app.infrastructure.repositories.sqlalchemy_appointment_repository import SQLAlchemyAppointmentRepository
from app.infrastructure.repositories.sqlalchemy_extraction_center_repository import SQLAlchemyExtractionCenterRepository
from app.infrastructure.repositories.sqlalchemy_study_repository import SQLAlchemyStudyRepository
from app.main import app
from app.use_cases.appointments import AppointmentService
from app.use_cases.studies import StudyService

PASSWORD = "appointments-api-test-password"
TEST_HASH = hash_password(PASSWORD)
SOFIA, OTHER_PATIENT, UNLINKED_PATIENT, DOCTOR, ADMIN = 1, 2, 3, 4, 5
PAID, AUTHORIZED, PENDING, REJECTED, OTHERS_STUDY = 1, 2, 3, 4, 5
MONDAY_10 = "2026-11-02T10:00:00-03:00"
NOW = datetime(2026, 11, 1, 10, tzinfo=TIMEZONE)  # domingo


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "appointments-api-test-secret-at-least-32-bytes")
    engine = create_engine(f"sqlite:///{tmp_path / 'api-appointments.db'}", connect_args={"check_same_thread": False})
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    roles = {SOFIA: "patient", OTHER_PATIENT: "patient", UNLINKED_PATIENT: "patient",
             DOCTOR: "treating_physician", ADMIN: "lab_administrator"}
    with Session(engine) as session:
        # Sin relaciones ORM la sesión no ordena por FK: se inserta en orden.
        for rows in (
            [Usuario(id=i, username=f"demo{i}", role=role, first_name="Demo", last_name="Prueba", phone="000",
                     email=f"demo{i}@example.test", password_hash=TEST_HASH) for i, role in roles.items()],
            [Paciente(id=1, dni="45000001", nombre="Sofía", apellido="DEMO", usuario_id=SOFIA),
             Paciente(id=2, dni="45000002", nombre="Otro", apellido="DEMO", usuario_id=OTHER_PATIENT)],
            [StudyModel(id=PAID, patient_id=1, status="pagado"),
             StudyModel(id=AUTHORIZED, patient_id=1, status="autorizado"),
             StudyModel(id=PENDING, patient_id=1, status="pendiente_pago"),
             StudyModel(id=REJECTED, patient_id=1, status="rechazado"),
             StudyModel(id=OTHERS_STUDY, patient_id=2, status="pagado")],
        ):
            session.add_all(rows)
            session.flush()
        session.commit()
    seed_demo_extraction_centers(sessionmaker(engine), year=2026)

    def database_session():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_database_session] = database_session
    app.dependency_overrides[get_clock] = lambda: NOW
    try:
        with TestClient(app) as http:
            yield http, engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def login(http, identifier=SOFIA):
    result = http.post("/api/auth/login", json={"email": f"demo{identifier}@example.test", "password": PASSWORD})
    assert result.status_code == 200
    return {"Authorization": "Bearer " + result.json()["access_token"]}


def book(http, study_id=PAID, starts_at=MONDAY_10, center_id=1, user=SOFIA):
    return http.post("/api/appointments", headers=login(http, user),
                     json={"study_id": study_id, "center_id": center_id, "starts_at": starts_at})


def study_status(engine, study_id):
    with Session(engine) as session:
        return session.get(StudyModel, study_id).status


def appointment_count(engine):
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(AppointmentModel))


def monday_slots(http):
    return http.get("/api/extraction-centers/1/slots", headers=login(http), params={"date": "2026-11-02"}).json()["slots"]


# Reservar

def test_booking_returns_the_appointment_and_marks_the_study(client):
    http, engine = client
    response = book(http)
    assert response.status_code == 201
    body = response.json()
    assert body["starts_at"] == MONDAY_10 and body["status"] == "booked" and body["study_id"] == PAID
    assert body["center"]["id"] == 1 and body["center"]["name"]
    assert study_status(engine, PAID) == "turno_sacado"
    with Session(engine) as session:
        assert session.get(AppointmentModel, body["id"]).study_status_before == "pagado"
    assert MONDAY_10 not in monday_slots(http)


@pytest.mark.parametrize("starts_at", [
    "2026-11-07T10:00:00-03:00",  # sábado
    "2026-12-08T10:00:00-03:00",  # feriado
    "2026-11-02T18:00:00-03:00",  # cierre
    "2026-11-02T09:10:00-03:00",  # fuera de los 15 minutos
    "2026-10-30T10:00:00-03:00",  # viernes pasado según el reloj
    "2026-11-02T10:00:00",        # sin zona horaria
])
def test_invalid_or_past_slot_is_422(client, starts_at):
    http, engine = client
    assert book(http, starts_at=starts_at).status_code == 422
    assert appointment_count(engine) == 0 and study_status(engine, PAID) == "pagado"


def test_same_center_and_slot_twice_is_one_201_and_one_409(client):
    http, engine = client
    assert book(http, PAID).status_code == 201
    second = book(http, AUTHORIZED, starts_at="2026-11-02T13:00:00+00:00")  # mismas 10:00 en UTC
    assert second.status_code == 409
    assert second.json()["detail"] == "El horario ya está reservado en este centro."
    assert study_status(engine, AUTHORIZED) == "autorizado" and appointment_count(engine) == 1


def test_study_with_another_booked_appointment_is_409(client):
    http, engine = client
    assert book(http, PAID).status_code == 201
    with Session(engine) as session:  # simula dos reservas simultáneas del mismo estudio
        session.get(StudyModel, PAID).status = "pagado"
        session.commit()
    response = book(http, PAID, starts_at="2026-11-02T11:00:00-03:00")
    assert response.status_code == 409 and response.json()["detail"] == "El estudio ya tiene un turno vigente."
    assert appointment_count(engine) == 1


@pytest.mark.parametrize("study_id, status", [(PENDING, "pendiente_pago"), (REJECTED, "rechazado")])
def test_study_not_enabled_is_409(client, study_id, status):
    http, engine = client
    response = book(http, study_id)
    assert response.status_code == 409 and "no está habilitado" in response.json()["detail"]
    assert appointment_count(engine) == 0 and study_status(engine, study_id) == status


@pytest.mark.parametrize("study_id, user", [(OTHERS_STUDY, SOFIA), (999, SOFIA), (PAID, UNLINKED_PATIENT)])
def test_foreign_missing_or_unlinked_study_is_404(client, study_id, user):
    http, engine = client
    response = book(http, study_id, user=user)
    assert response.status_code == 404 and response.json()["detail"] == "El estudio no existe o no es tuyo."
    assert study_status(engine, OTHERS_STUDY) == "pagado" and appointment_count(engine) == 0


def test_missing_or_inactive_center_is_404(client):
    http, engine = client
    with Session(engine) as session:
        session.get(ExtractionCenterModel, 2).active = False
        session.commit()
    for center_id in (2, 9999):
        response = book(http, center_id=center_id)
        assert response.status_code == 404
        assert response.json()["detail"] == "El centro de extracción no existe o no está activo."


def test_if_the_study_change_fails_no_appointment_is_left(client):
    _, engine = client

    class FailingStudyService(StudyService):
        def cambiar_estado_estudio(self, study_id, nuevo_estado):
            super().cambiar_estado_estudio(study_id, nuevo_estado)
            raise RuntimeError("falla simulada del módulo de estudios")

    with Session(engine) as session:
        service = AppointmentService(SQLAlchemyAppointmentRepository(session),
                                     SQLAlchemyExtractionCenterRepository(session),
                                     FailingStudyService(SQLAlchemyStudyRepository(session)))
        with pytest.raises(RuntimeError):
            service.reservar(SOFIA, PAID, 1, datetime.fromisoformat(MONDAY_10), NOW)
    assert appointment_count(engine) == 0 and study_status(engine, PAID) == "pagado"


# Cancelar

def test_cancel_and_book_again_end_to_end(client):
    http, engine = client
    appointment_id = book(http, AUTHORIZED).json()["id"]
    assert http.get(f"/api/studies/{AUTHORIZED}/appointment", headers=login(http)).status_code == 200
    assert study_status(engine, AUTHORIZED) == "turno_sacado"

    assert http.delete(f"/api/appointments/{appointment_id}", headers=login(http)).status_code == 204
    assert study_status(engine, AUTHORIZED) == "autorizado"
    with Session(engine) as session:
        cancelled = session.get(AppointmentModel, appointment_id)
        assert cancelled.status == "cancelled" and cancelled.cancelled_at == NOW
    assert http.get(f"/api/studies/{AUTHORIZED}/appointment", headers=login(http)).status_code == 404
    assert MONDAY_10 in monday_slots(http)

    again = book(http, AUTHORIZED)
    assert again.status_code == 201 and again.json()["starts_at"] == MONDAY_10
    assert study_status(engine, AUTHORIZED) == "turno_sacado"


def test_cancel_rules(client):
    http, engine = client
    appointment_id = book(http).json()["id"]
    for user in (DOCTOR, ADMIN):
        assert http.delete(f"/api/appointments/{appointment_id}", headers=login(http, user)).status_code == 403
    for identifier, user in ((appointment_id, OTHER_PATIENT), (999, SOFIA)):
        response = http.delete(f"/api/appointments/{identifier}", headers=login(http, user))
        assert response.status_code == 404 and response.json()["detail"] == "El turno no existe."
    assert study_status(engine, PAID) == "turno_sacado"
    assert http.delete(f"/api/appointments/{appointment_id}", headers=login(http)).status_code == 204
    again = http.delete(f"/api/appointments/{appointment_id}", headers=login(http))
    assert again.status_code == 409 and again.json()["detail"] == "Solo se puede cancelar un turno reservado."
    assert study_status(engine, PAID) == "pagado"


@pytest.mark.parametrize("now", [datetime(2026, 11, 2, 10, tzinfo=TIMEZONE), datetime(2026, 11, 3, 9, tzinfo=TIMEZONE)])
def test_an_appointment_that_already_started_cannot_be_cancelled(client, now):
    http, engine = client
    appointment_id = book(http).json()["id"]
    app.dependency_overrides[get_clock] = lambda: now
    response = http.delete(f"/api/appointments/{appointment_id}", headers=login(http))
    assert response.status_code == 409 and response.json()["detail"] == "No se puede cancelar un turno que ya empezó."
    assert study_status(engine, PAID) == "turno_sacado"
    with Session(engine) as session:
        assert session.get(AppointmentModel, appointment_id).status == "booked"


def test_cancel_does_not_move_back_a_study_that_advanced(client):
    http, engine = client
    appointment_id = book(http).json()["id"]
    with Session(engine) as session:  # p. ej., el aviso de extracción de T03
        session.get(StudyModel, PAID).status = "listo_para_retirar"
        session.commit()
    response = http.delete(f"/api/appointments/{appointment_id}", headers=login(http))
    assert response.status_code == 409
    assert response.json()["detail"] == "El turno ya no se puede cancelar: el estudio pasó a otra etapa."
    assert study_status(engine, PAID) == "listo_para_retirar"
    with Session(engine) as session:
        assert session.get(AppointmentModel, appointment_id).status == "booked"


# Turno del estudio

def test_study_appointment_for_its_owner_only(client):
    http, _ = client
    book(http)
    response = http.get(f"/api/studies/{PAID}/appointment", headers=login(http))
    assert response.status_code == 200
    body = response.json()
    assert body["starts_at"] == MONDAY_10
    assert set(body["center"]) == {"id", "name", "address", "city", "phone"}
    foreign = http.get(f"/api/studies/{PAID}/appointment", headers=login(http, OTHER_PATIENT))
    assert foreign.status_code == 404 and foreign.json()["detail"] == "El estudio no existe o no es tuyo."
    without = http.get(f"/api/studies/{AUTHORIZED}/appointment", headers=login(http))
    assert without.status_code == 404 and without.json()["detail"] == "El estudio no tiene un turno vigente."


# Asistencia

def test_attendance_and_absence_counter(client):
    http, _ = client
    first = book(http, PAID).json()["id"]
    second = book(http, AUTHORIZED, starts_at="2026-11-02T11:00:00-03:00").json()["id"]
    admin = login(http, ADMIN)
    attended = http.patch(f"/api/appointments/{first}/attendance", headers=admin, json={"attended": True})
    assert attended.status_code == 200
    assert attended.json() == {"id": first, "status": "attended", "patient_absences": 0}
    absent = http.patch(f"/api/appointments/{second}/attendance", headers=admin, json={"attended": False})
    assert absent.json() == {"id": second, "status": "absent", "patient_absences": 1}


def test_attendance_rules(client):
    http, _ = client
    booked = book(http, PAID).json()["id"]
    cancelled = book(http, AUTHORIZED, starts_at="2026-11-02T11:00:00-03:00").json()["id"]
    http.delete(f"/api/appointments/{cancelled}", headers=login(http))
    for user in (SOFIA, DOCTOR):
        response = http.patch(f"/api/appointments/{booked}/attendance", headers=login(http, user),
                              json={"attended": True})
        assert response.status_code == 403
    admin = login(http, ADMIN)
    assert http.patch("/api/appointments/999/attendance", headers=admin, json={"attended": True}).status_code == 404
    assert http.patch(f"/api/appointments/{booked}/attendance", headers=admin, json={"attended": True}).status_code == 200
    for identifier in (booked, cancelled):
        response = http.patch(f"/api/appointments/{identifier}/attendance", headers=admin, json={"attended": False})
        assert response.status_code == 409
        assert response.json()["detail"] == "Solo se registra la asistencia de un turno reservado."


# Sin sesión

def test_endpoints_require_a_session(client):
    http, _ = client
    assert http.post("/api/appointments", json={}).status_code == 401
    assert http.delete("/api/appointments/1").status_code == 401
    assert http.get("/api/studies/1/appointment").status_code == 401
    assert http.patch("/api/appointments/1/attendance", json={"attended": True}).status_code == 401


# Mis turnos y estudios para sacar turno

def test_my_appointments_lists_only_my_booked_ones_in_order(client):
    http, _ = client
    later = book(http, PAID, starts_at="2026-11-03T10:00:00-03:00").json()["id"]
    earlier = book(http, AUTHORIZED).json()["id"]
    book(http, OTHERS_STUDY, starts_at="2026-11-02T11:00:00-03:00", user=OTHER_PATIENT)
    mine = http.get("/api/appointments/mine", headers=login(http)).json()
    assert [a["id"] for a in mine] == [earlier, later]
    assert mine[0]["study_code"] == "EST-000002" and mine[0]["starts_at"] == MONDAY_10
    assert set(mine[0]["center"]) == {"id", "name", "address", "city", "phone"}
    http.delete(f"/api/appointments/{earlier}", headers=login(http))
    assert [a["id"] for a in http.get("/api/appointments/mine", headers=login(http)).json()] == [later]
    assert http.get("/api/appointments/mine", headers=login(http, UNLINKED_PATIENT)).json() == []


def test_eligible_studies_are_paid_or_authorized_without_booking(client):
    http, _ = client
    eligible = lambda: http.get("/api/appointments/eligible-studies", headers=login(http)).json()
    assert eligible() == [{"id": PAID, "code": "EST-000001", "status": "pagado"},
                          {"id": AUTHORIZED, "code": "EST-000002", "status": "autorizado"}]
    appointment_id = book(http, PAID).json()["id"]
    assert [s["id"] for s in eligible()] == [AUTHORIZED]
    http.delete(f"/api/appointments/{appointment_id}", headers=login(http))
    assert [s["id"] for s in eligible()] == [PAID, AUTHORIZED]
    other = http.get("/api/appointments/eligible-studies", headers=login(http, OTHER_PATIENT)).json()
    assert [s["id"] for s in other] == [OTHERS_STUDY]


def test_my_appointments_and_eligible_studies_are_for_patients_only(client):
    http, _ = client
    for path in ("/api/appointments/mine", "/api/appointments/eligible-studies"):
        assert http.get(path).status_code == 401
        for user in (DOCTOR, ADMIN):
            assert http.get(path, headers=login(http, user)).status_code == 403
