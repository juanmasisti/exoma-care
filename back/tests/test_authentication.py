from fastapi.testclient import TestClient

from app.api.dependencies import get_authenticate_user_use_case
from app.domain.entities.roles import UserRole
from app.domain.entities.user import UserAccount
from app.infrastructure.database.security import hash_password
from app.main import app
from app.use_cases.authentication import AutenticarUsuarioUseCase


class InMemoryUserRepository:
    def __init__(self, account: UserAccount) -> None:
        self._account = account

    def get_by_email(self, email: str) -> UserAccount | None:
        return self._account if self._account.email == email else None


def create_use_case(role: UserRole) -> AutenticarUsuarioUseCase:
    return AutenticarUsuarioUseCase(
        InMemoryUserRepository(
            UserAccount(
                id=1,
                email="paciente@example.test",
                password_hash=hash_password("correct-password"),
                role=role,
            )
        )
    )


def test_patient_login_returns_patient_dashboard(monkeypatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-only-secret-with-at-least-32-bytes")
    app.dependency_overrides[get_authenticate_user_use_case] = lambda: create_use_case(
        UserRole.PATIENT
    )

    try:
        response = TestClient(app).post(
            "/api/auth/login",
            json={
                "email": "paciente@example.test",
                "password": "correct-password",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["rol"] == "Paciente"
    assert response.json()["role"] == "patient"
    assert response.json()["redirect_to"] == "/paciente/dashboard"
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_non_patient_login_does_not_redirect_to_patient_dashboard(
    monkeypatch,
) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-only-secret-with-at-least-32-bytes")
    app.dependency_overrides[get_authenticate_user_use_case] = lambda: create_use_case(
        UserRole.TREATING_PHYSICIAN
    )

    try:
        response = TestClient(app).post(
            "/api/auth/login",
            json={
                "email": "paciente@example.test",
                "password": "correct-password",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["rol"] == "Médico"
    assert response.json()["role"] == "treating_physician"
    assert "redirect_to" not in response.json()


def test_login_rejects_invalid_password(monkeypatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-only-secret-with-at-least-32-bytes")
    app.dependency_overrides[get_authenticate_user_use_case] = lambda: create_use_case(
        UserRole.PATIENT
    )

    try:
        response = TestClient(app).post(
            "/api/auth/login",
            json={
                "email": "paciente@example.test",
                "password": "wrong-password",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
