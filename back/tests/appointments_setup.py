"""Armado común de las pruebas de la API de turnos: base temporal, usuarios, estudios, reloj y helpers."""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_database_session
from app.api.routes.extraction_centers import get_clock
from app.domain.entities.logistics import TIMEZONE
from app.infrastructure.database.logistics_models import AppointmentModel
from app.infrastructure.database.models import Paciente, Usuario
from app.infrastructure.database.security import hash_password
from app.infrastructure.database.seed_demo_extraction_centers import seed_demo_extraction_centers
from app.infrastructure.database.session import Base
from app.infrastructure.database.study_models import StudyModel
from app.main import app


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
