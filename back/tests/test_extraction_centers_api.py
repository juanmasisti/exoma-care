from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_database_session
from app.api.routes.extraction_centers import get_clock
from app.domain.entities.logistics import TIMEZONE
from app.infrastructure.database.logistics_models import ExtractionCenterModel, ProvinceModel
from app.infrastructure.database.models import Usuario
from app.infrastructure.database.security import hash_password
from app.infrastructure.database.seed_demo_extraction_centers import seed_demo_extraction_centers
from app.infrastructure.database.session import Base
from app.main import app

TEST_HASH = hash_password("centers-api-test-password")
MONDAY, SATURDAY, HOLIDAY = "2026-11-02", "2026-11-07", "2026-12-08"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "centers-api-test-secret-at-least-32-bytes")
    engine = create_engine(f"sqlite:///{tmp_path / 'api-centers.db'}", connect_args={"check_same_thread": False})
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for identifier, role in enumerate(["patient", "treating_physician"], 1):
            session.add(Usuario(id=identifier, username=f"demo{identifier}", role=role, first_name="Demo",
                                last_name="Prueba", phone="000", email=f"demo{identifier}@example.test",
                                password_hash=TEST_HASH))
        session.commit()
    seed_demo_extraction_centers(sessionmaker(engine), year=2026)

    def database_session():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_database_session] = database_session
    app.dependency_overrides[get_clock] = lambda: datetime(2026, 11, 1, 10, tzinfo=TIMEZONE)
    try:
        with TestClient(app) as http:
            yield http, engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def login(http, identifier=1):
    result = http.post("/api/auth/login", json={"email": f"demo{identifier}@example.test",
                                                "password": "centers-api-test-password"})
    assert result.status_code == 200
    return {"Authorization": "Bearer " + result.json()["access_token"]}


def province_id(engine, name):
    with Session(engine) as session:
        return session.scalar(select(ProvinceModel.id).where(ProvinceModel.name == name))


def test_provinces_and_centers_after_seed_with_filters(client):
    http, engine = client
    headers = login(http)
    provinces = http.get("/api/provinces", headers=headers).json()
    assert len(provinces) == 24 and sum(p["active_centers"] for p in provinces) == 100
    assert len(http.get("/api/extraction-centers", headers=headers).json()) == 100
    caba = http.get("/api/extraction-centers", headers=headers,
                    params={"province_id": province_id(engine, "Ciudad Autónoma de Buenos Aires")}).json()
    assert len(caba) == 10 and {c["city"] for c in caba} == {"Ciudad de Buenos Aires"}
    posadas = http.get("/api/extraction-centers", headers=headers, params={"q": " POSADAS "}).json()
    assert [c["city"] for c in posadas] == ["Posadas"] * 3


def test_inactive_center_is_hidden_and_its_slots_are_not_found(client):
    http, engine = client
    headers = login(http)
    with Session(engine) as session:
        first, second = session.scalars(select(ExtractionCenterModel).where(ExtractionCenterModel.city == "Ushuaia"))
        first.active = second.active = False
        session.commit()
        center_id = first.id
    assert center_id not in {c["id"] for c in http.get("/api/extraction-centers", headers=headers).json()}
    provinces = http.get("/api/provinces", headers=headers).json()
    assert len(provinces) == 24
    assert next(p for p in provinces if p["name"] == "Tierra del Fuego")["active_centers"] == 0
    for identifier in (center_id, 9999):
        response = http.get(f"/api/extraction-centers/{identifier}/slots", headers=headers, params={"date": MONDAY})
        assert response.status_code == 404
        assert response.json()["detail"] == "El centro de extracción no existe o no está activo."


def test_business_day_saturday_and_holiday_slots(client):
    http, _ = client
    headers = login(http)
    monday = http.get("/api/extraction-centers/1/slots", headers=headers, params={"date": MONDAY}).json()
    assert monday["business_day"] is True and monday["holiday"] is None
    assert len(monday["slots"]) == 36
    assert monday["slots"][0] == "2026-11-02T09:00:00-03:00" and monday["slots"][-1] == "2026-11-02T17:45:00-03:00"
    saturday = http.get("/api/extraction-centers/1/slots", headers=headers, params={"date": SATURDAY}).json()
    assert saturday["business_day"] is False and saturday["slots"] == []
    holiday = http.get("/api/extraction-centers/1/slots", headers=headers, params={"date": HOLIDAY}).json()
    assert holiday["business_day"] is False and holiday["slots"] == []
    assert holiday["holiday"] == "Inmaculada Concepción de María"
    past = http.get("/api/extraction-centers/1/slots", headers=headers, params={"date": "2026-10-30"}).json()
    assert past["business_day"] is True and past["slots"] == []


def test_slots_already_started_are_not_offered(client):
    http, _ = client
    app.dependency_overrides[get_clock] = lambda: datetime(2026, 11, 2, 12, 5, tzinfo=TIMEZONE)
    response = http.get("/api/extraction-centers/1/slots", headers=login(http), params={"date": MONDAY})
    assert response.json()["slots"][0] == "2026-11-02T12:15:00-03:00"


def test_authentication_role_and_date_validation(client):
    http, _ = client
    assert http.get("/api/provinces").status_code == 401
    assert http.get("/api/extraction-centers").status_code == 401
    assert http.get("/api/extraction-centers/1/slots", params={"date": MONDAY}).status_code == 401
    doctor = login(http, 2)
    assert http.get("/api/provinces", headers=doctor).status_code == 403
    assert http.get("/api/extraction-centers", headers=doctor).status_code == 403
    assert http.get("/api/extraction-centers/1/slots", headers=doctor, params={"date": MONDAY}).status_code == 403
    headers = login(http)
    for params in ({}, {"date": "2026-13-01"}, {"date": "02/11/2026"}):
        assert http.get("/api/extraction-centers/1/slots", headers=headers, params=params).status_code == 422
    assert http.get("/api/extraction-centers", headers=headers, params={"q": "x" * 101}).status_code == 422
