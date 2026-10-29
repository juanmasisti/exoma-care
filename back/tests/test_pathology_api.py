from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.api.dependencies import get_database_session
from app.domain.entities.roles import UserRole
from app.infrastructure.database.models import Usuario
from app.infrastructure.database.catalog_models import SymptomModel
from app.infrastructure.database.security import hash_password
from app.infrastructure.database.session import Base
from app.main import app

SECRET = "test-only-catalog-secret-at-least-32-bytes"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", SECRET)
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}", connect_args={"check_same_thread": False})
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for i, role in enumerate([UserRole.MEDICAL_MANAGER, UserRole.TREATING_PHYSICIAN, UserRole.PATIENT], 1):
            session.add(Usuario(id=i, username=f"demo{i}", email=f"demo{i}@example.test", role=role,
                                first_name="Demo", last_name="Prueba", phone="000",
                                password_hash=hash_password("test-only-password")))
        session.add_all([SymptomModel(id=i, code=f"DEMO-{i}", code_system="DEMO", label=f"Demo {i}")
                         for i in range(1, 5)])
        session.commit()
    def database_session():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_database_session] = database_session
    try:
        with TestClient(app) as test_client:
            yield test_client, engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def login(client, user=1):
    response = client.post("/api/auth/login", json={"email": f"demo{user}@example.test", "password": "test-only-password"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def definition():
    return {"name": "Patología de prueba", "cardinal_symptom_id": 1, "secondary_symptom_ids": [2, 3]}


def test_real_login_create_edit_and_validate(client):
    http, _ = client
    manager = login(http)
    response = http.post("/api/pathologies", json=definition(), headers=manager)
    assert response.status_code == 201
    pathology_id = response.json()["id"]
    physician = login(http, 2)
    assert http.get("/api/pathologies", headers=physician).json()[0]["id"] == pathology_id
    assert http.get(f"/api/pathologies/{pathology_id}", headers=physician).status_code == 200
    for ids, valid in [([1], True), ([2, 3], True), ([2, 2], False), ([], False)]:
        result = http.post(f"/api/pathologies/{pathology_id}/validate-suspicion",
                           json={"symptom_ids": ids}, headers=physician)
        assert result.status_code == 200
        assert result.json()["valid"] is valid
    changed = {**definition(), "name": "Editada", "cardinal_symptom_id": 4}
    assert http.put(f"/api/pathologies/{pathology_id}", json=changed, headers=manager).status_code == 200
    assert http.get(f"/api/pathologies/{pathology_id}", headers=physician).json()["cardinal_symptom"]["id"] == 4


def test_permissions_are_enforced_by_api(client):
    http, _ = client
    assert http.get("/api/pathologies").status_code == 401
    physician = login(http, 2)
    assert http.post("/api/pathologies", json=definition(), headers=physician).status_code == 403
    patient = login(http, 3)
    assert http.get("/api/pathologies", headers=patient).status_code == 403
    assert http.get("/api/symptoms", headers=patient).status_code == 403


@pytest.mark.parametrize("token", ["invalid", jwt.encode({"sub": "1"}, SECRET, algorithm="HS256"),
    jwt.encode({"sub": "1", "iat": datetime.now(timezone.utc) - timedelta(hours=2),
                "exp": datetime.now(timezone.utc) - timedelta(hours=1)}, SECRET, algorithm="HS256"),
    jwt.encode({"sub": "999", "iat": datetime.now(timezone.utc),
                "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, SECRET, algorithm="HS256"),
    jwt.encode({"sub": "1", "iat": datetime.now(timezone.utc),
                "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "wrong-signing-key-at-least-32-bytes", algorithm="HS256")])
def test_invalid_expired_or_unknown_session(client, token):
    http, _ = client
    assert http.get("/api/pathologies", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_current_role_is_loaded_from_database(client):
    http, engine = client
    headers = login(http)
    with Session(engine) as session:
        session.get(Usuario, 1).role = UserRole.PATIENT
        session.commit()
    assert http.post("/api/pathologies", json=definition(), headers=headers).status_code == 403


def test_invalid_definitions_duplicates_and_not_found(client):
    http, _ = client
    headers = login(http)
    for patch in [{"name": " "}, {"cardinal_symptom_id": 999}, {"secondary_symptom_ids": [1]},
                  {"secondary_symptom_ids": [999]}, {"cardinal_symptom_id": 0}, {"unexpected": True}]:
        assert http.post("/api/pathologies", json={**definition(), **patch}, headers=headers).status_code == 422
    assert http.post("/api/pathologies", json=definition(), headers=headers).status_code == 201
    assert http.post("/api/pathologies", json={**definition(), "name": "PATOLOGÍA DE PRUEBA"}, headers=headers).status_code == 409
    assert http.get("/api/pathologies/999", headers=headers).status_code == 404
    assert http.put("/api/pathologies/999", json=definition(), headers=headers).status_code == 404
    assert http.get("/api/pathologies/0", headers=headers).status_code == 422


def test_symptom_search_and_unknown_validation_input(client):
    http, _ = client
    headers = login(http)
    response = http.get("/api/symptoms?q=DEMO-2", headers=headers)
    assert [s["id"] for s in response.json()] == [2]
    assert response.json()[0]["code_system"] == "DEMO"
    assert http.get("/api/symptoms?q=%25", headers=headers).json() == []
    pathology_id = http.post("/api/pathologies", json=definition(), headers=headers).json()["id"]
    assert http.post(f"/api/pathologies/{pathology_id}/validate-suspicion",
                     json={"symptom_ids": [1, 999]}, headers=headers).status_code == 422
