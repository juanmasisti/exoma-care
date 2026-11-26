import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_database_session, get_notification_service
from app.config import Settings
from app.domain.dtos.notification_dto import NotificacionInput
from app.domain.entities.roles import UserRole
from app.infrastructure.database.models import NotificacionLog, Usuario
from app.infrastructure.database.session import Base
from app.infrastructure.external_services.errors import ExternalServiceError
from app.infrastructure.external_services.notification_client import (
    IdempotencyConflictError,
    TTPSNotificationClient,
)
from app.infrastructure.repositories.sqlalchemy_notification_log_repository import (
    SQLAlchemyNotificationLogRepository,
)
from app.main import app
from app.use_cases.notifications import EnviarNotificacionUseCase

AVISO_ID = "00000000-0000-4000-8000-000000000001"


def valid_input(**overrides):
    values = {
        "asunto": "Resultado disponible",
        "mensaje": "El resultado está listo.",
        "destinatarios": ["paciente@example.test"],
        "idempotency_key": "estudio-123-resultado",
        "referencia": "ESTUDIO-123",
    }
    values.update(overrides)
    return NotificacionInput(**values)


@pytest.mark.parametrize(
    "overrides",
    [
        {"asunto": " "},
        {"asunto": "a" * 201},
        {"mensaje": "m" * 10_001},
        {"idempotency_key": "k" * 201},
        {"destinatarios": []},
        {"destinatarios": ["not-an-email"]},
        {"destinatarios": ["a" * 321 + "@example.test"]},
        {"destinatarios": ["a@example.test"] * 51},
    ],
)
def test_notification_input_validates_api_constraints(overrides):
    with pytest.raises(ValidationError):
        valid_input(**overrides)


def test_notification_client_sends_contract_and_reuses_key_on_retry():
    sent_requests = []

    async def responder(request):
        sent_requests.append(request)
        if len(sent_requests) == 1:
            return httpx.Response(500, json={"error": "temporary"})
        return httpx.Response(
            202,
            json={"id": AVISO_ID, "estado": "pendiente", "creado": True},
        )

    async def run():
        client = TTPSNotificationClient(
            "test-api-key",
            base_url="https://notifications.example.test/functions/v1",
            transport=httpx.MockTransport(responder),
        )
        return await client.enviar_aviso(valid_input())

    resultado = asyncio.run(run())
    assert resultado.aviso_id == AVISO_ID
    assert resultado.estado == "pendiente"
    assert resultado.creado is True
    assert len(sent_requests) == 2
    assert sent_requests[0].headers["X-API-Key"] == "test-api-key"
    assert sent_requests[0].headers["Idempotency-Key"] == "estudio-123-resultado"
    assert sent_requests[0].headers["Content-Type"] == "application/json"
    assert sent_requests[0].content == sent_requests[1].content
    assert sent_requests[0].headers["Idempotency-Key"] == sent_requests[
        1
    ].headers["Idempotency-Key"]
    import json

    payload = json.loads(sent_requests[0].content)
    assert payload["referencia"] == "ESTUDIO-123"
    assert payload["destinatarios"] == [
        {"canal": "email", "destino": "paciente@example.test"}
    ]


def test_notification_client_raises_specific_idempotency_conflict():
    async def responder(_request):
        return httpx.Response(409, json={"error": "key reused"})

    async def run():
        client = TTPSNotificationClient(
            "test-api-key", transport=httpx.MockTransport(responder)
        )
        with pytest.raises(IdempotencyConflictError, match="key reused"):
            await client.enviar_aviso(valid_input())

    asyncio.run(run())


def test_notification_client_raises_api_error_field_and_checks_pending_limit():
    async def responder(_request):
        return httpx.Response(403, json={"error": "forbidden"})

    async def run():
        client = TTPSNotificationClient(
            "test-api-key", transport=httpx.MockTransport(responder)
        )
        with pytest.raises(ExternalServiceError, match="forbidden") as failure:
            await client.verificar_conexion()
        assert failure.value.status_code == 403
        with pytest.raises(ValueError, match="limite"):
            await client.listar_pendientes(101)

    asyncio.run(run())


def test_notification_use_case_persists_idempotent_audit_log(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'notifications.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    class FakeNotificationService:
        async def enviar_aviso(self, _datos):
            from app.domain.dtos.notification_dto import NotificacionResultado

            return NotificacionResultado(
                aviso_id=AVISO_ID, estado="pendiente", creado=True
            )

        async def verificar_conexion(self):
            return {}

        async def consultar_estado(self, _aviso_id):
            return {}

        async def listar_pendientes(self, _limite=25):
            return {}

    with factory() as session:
        use_case = EnviarNotificacionUseCase(
            FakeNotificationService(), SQLAlchemyNotificationLogRepository(session)
        )
        datos = valid_input()
        first = asyncio.run(use_case.execute(datos))
        second = asyncio.run(use_case.execute(datos))
        assert first.aviso_id == second.aviso_id == AVISO_ID

    with factory() as session:
        logs = session.scalars(select(NotificacionLog)).all()
        assert len(logs) == 1
        assert logs[0].idempotency_key == "estudio-123-resultado"
        assert logs[0].referencia == "ESTUDIO-123"
        assert logs[0].estado_inicial == "pendiente"
    engine.dispose()


def test_notification_settings_accept_canonical_env_names():
    settings = Settings(
        _env_file=None,
        NOTIFICATIONS_BASE_URL="https://notifications.example.test/functions/v1",
        NOTIFICATIONS_API_KEY="test-key",
    )
    assert settings.notifications_base_url.endswith("/v1")
    assert settings.notification_api_key.get_secret_value() == "test-key"


def test_notification_monitoring_routes_are_super_admin_only(tmp_path, monkeypatch):
    secret = "notifications-api-test-secret-at-least-32-bytes"
    monkeypatch.setenv("JWT_SECRET_KEY", secret)
    engine = create_engine(f"sqlite:///{tmp_path / 'notifications-api.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                Usuario(
                    id=user_id,
                    username=f"notify-user-{user_id}",
                    email=f"notify{user_id}@example.test",
                    role=role,
                    first_name="Demo",
                    last_name="User",
                    phone="000",
                    password_hash="test-hash",
                )
                for user_id, role in (
                    (1, UserRole.SUPER_ADMIN),
                    (2, UserRole.PATIENT),
                )
            ]
        )
        session.commit()

    class FakeNotificationService:
        async def verificar_conexion(self):
            return {"mensaje": "Autenticación exitosa"}

        async def consultar_estado(self, aviso_id):
            return {"id": aviso_id, "estado": "pendiente", "envios": []}

        async def listar_pendientes(self, limite=25):
            return {"avisos": [], "limite": limite}

    def database_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_database_session] = database_session
    app.dependency_overrides[get_notification_service] = lambda: FakeNotificationService()

    def token(user_id):
        now = datetime.now(timezone.utc)
        encoded = jwt.encode(
            {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=5)},
            secret,
            algorithm="HS256",
        )
        return {"Authorization": f"Bearer {encoded}"}

    try:
        with TestClient(app) as client:
            assert client.get("/api/notificaciones/health").status_code == 401
            assert (
                client.get(
                    "/api/notificaciones/health", headers=token(2)
                ).status_code
                == 403
            )
            health = client.get(
                "/api/notificaciones/health", headers=token(1)
            )
            assert health.json()["mensaje"] == "Autenticación exitosa"
            pending = client.get(
                "/api/notificaciones/pendientes?limite=10", headers=token(1)
            )
            assert pending.json()["limite"] == 10
            state = client.get(
                f"/api/notificaciones/{UUID(AVISO_ID)}", headers=token(1)
            )
            assert state.json()["estado"] == "pendiente"
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
