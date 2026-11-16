import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.dependencies import get_database_session
from app.domain.entities.roles import UserRole
from app.infrastructure.database.models import Usuario
from app.infrastructure.database.security import hash_password, verify_password
from app.infrastructure.database.session import Base
from app.main import app

SECRET = "test-only-admin-secret-with-at-least-32-bytes"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", SECRET)
    engine = create_engine(f"sqlite:///{tmp_path / 'admin-users.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                Usuario(
                    id=1,
                    username="superadmin@example.test",
                    role=UserRole.SUPER_ADMIN,
                    first_name="Super",
                    last_name="Admin",
                    phone="000",
                    email="superadmin@example.test",
                    password_hash=hash_password("test-only-password"),
                ),
                Usuario(
                    id=2,
                    username="doctor@example.test",
                    role=UserRole.TREATING_PHYSICIAN,
                    first_name="Doctora",
                    last_name="Demo",
                    phone="000",
                    email="doctor@example.test",
                    password_hash=hash_password("test-only-password"),
                ),
            ]
        )
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


def login(client, email="superadmin@example.test"):
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "test-only-password"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def physician_data():
    return {
        "role": "treating_physician",
        "first_name": "María",
        "last_name": "Gómez",
        "email": " MARIA.GOMEZ@example.test ",
        "phone": "+54 11 4000 0001",
        "license_number": "MN-1234",
        "specialty": "Genética médica",
    }


def test_admin_user_endpoints_require_super_admin(client):
    http, _ = client
    assert http.get("/api/admin/users").status_code == 401
    physician = login(http, "doctor@example.test")
    assert http.get("/api/admin/users", headers=physician).status_code == 403
    assert (
        http.post(
            "/api/admin/users",
            json=physician_data(),
            headers=physician,
        ).status_code
        == 403
    )


def test_super_admin_creates_physician_and_receives_temporary_password(client):
    http, engine = client
    admin = login(http)

    response = http.post(
        "/api/admin/users",
        json=physician_data(),
        headers=admin,
    )

    assert response.status_code == 201
    created = response.json()
    assert created["role"] == "treating_physician"
    assert created["email"] == "maria.gomez@example.test"
    assert created["license_number"] == "MN-1234"
    assert created["specialty"] == "Genética médica"
    assert created["temporary_password"]
    with Session(engine) as session:
        user = session.get(Usuario, created["id"])
        assert user is not None
        assert user.username == created["email"]
        assert verify_password(created["temporary_password"], user.password_hash)
    assert http.post(
        "/api/auth/login",
        json={
            "email": created["email"],
            "password": created["temporary_password"],
        },
    ).status_code == 200

    listed = http.get("/api/admin/users", headers=admin)
    assert listed.status_code == 200
    assert len(listed.json()) == 2
    assert all("temporary_password" not in user for user in listed.json())
    assert all("password_hash" not in user for user in listed.json())


@pytest.mark.parametrize(
    ("role", "extra_fields"),
    [
        ("lab_administrator", {}),
        ("bioinformatician", {}),
    ],
)
def test_super_admin_can_create_hu_roles(client, role, extra_fields):
    http, _ = client
    admin = login(http)
    payload = {
        "role": role,
        "first_name": "Usuario",
        "last_name": "Demo",
        "email": f"{role}@example.test",
        "phone": "000",
        **extra_fields,
    }

    response = http.post("/api/admin/users", json=payload, headers=admin)

    assert response.status_code == 201
    assert response.json()["role"] == role


def test_creation_rejects_duplicate_email_and_roles_outside_hu(client):
    http, _ = client
    admin = login(http)

    duplicate = http.post(
        "/api/admin/users",
        json={
            **physician_data(),
            "email": "doctor@example.test",
        },
        headers=admin,
    )
    unsupported_role = http.post(
        "/api/admin/users",
        json={**physician_data(), "role": "patient"},
        headers=admin,
    )
    missing_physician_fields = http.post(
        "/api/admin/users",
        json={
            "role": "treating_physician",
            "first_name": "María",
            "last_name": "Gómez",
            "email": "new@example.test",
            "phone": "000",
        },
        headers=admin,
    )

    assert duplicate.status_code == 409
    assert unsupported_role.status_code == 422
    assert missing_physician_fields.status_code == 422
