import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_database_session
from app.api.routes.transport import get_route_optimizer
from app.config import get_settings
from app.domain.interfaces.route_optimizer import RouteOptimizerError
from app.infrastructure.adapters.route_optimizer_client import RouteOptimizerClient
from app.infrastructure.database.logistics_models import ExtractionCenterModel
from app.infrastructure.database.models import Usuario
from app.infrastructure.database.security import hash_password
from app.infrastructure.database.seed_demo_extraction_centers import seed_demo_extraction_centers
from app.infrastructure.database.session import Base
from app.main import app

TEST_HASH = hash_password("route-preview-test-password")


class FakeOptimizer:
    """Doble del Protocol RouteOptimizer: anota cada llamada y responde con `answer`."""

    def __init__(self):
        self.calls = []
        self.answer = lambda points: points

    def order(self, points):
        self.calls.append(points)
        return self.answer(points)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "route-preview-test-secret-at-least-32-bytes")
    engine = create_engine(f"sqlite:///{tmp_path / 'route-preview.db'}", connect_args={"check_same_thread": False})
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for identifier, role in enumerate(["lab_administrator", "patient"], 1):
            session.add(Usuario(id=identifier, username=f"demo{identifier}", role=role, first_name="Demo",
                                last_name="Prueba", phone="000", email=f"demo{identifier}@example.test",
                                password_hash=TEST_HASH))
        session.commit()
    seed_demo_extraction_centers(sessionmaker(engine), year=2026)
    optimizer = FakeOptimizer()

    def database_session():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_database_session] = database_session
    app.dependency_overrides[get_route_optimizer] = lambda: optimizer
    try:
        with TestClient(app) as http:
            yield http, engine, optimizer
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def login(http, identifier=1):
    result = http.post("/api/auth/login", json={"email": f"demo{identifier}@example.test",
                                                "password": "route-preview-test-password"})
    assert result.status_code == 200
    return {"Authorization": "Bearer " + result.json()["access_token"]}


def center_ids(engine, amount):
    with Session(engine) as session:
        return list(session.scalars(select(ExtractionCenterModel.id).order_by(ExtractionCenterModel.id).limit(amount)))


def preview(http, ids, identifier=1):
    return http.post("/api/transport/route-preview", json={"center_ids": ids}, headers=login(http, identifier))


def test_centers_come_back_in_the_order_returned_by_the_api(client):
    http, engine, optimizer = client
    ids = center_ids(engine, 3)
    optimizer.answer = lambda points: [points[0], *reversed(points[1:-1]), points[-1]]
    response = preview(http, ids)
    assert response.status_code == 200
    assert [center["id"] for center in response.json()] == list(reversed(ids))
    settings = get_settings()
    lab = (settings.central_lab_latitude, settings.central_lab_longitude)
    (sent,) = optimizer.calls
    assert sent[0] == sent[-1] == lab and len(sent) == 5


def test_zero_or_one_center_does_not_call_the_api(client):
    http, engine, optimizer = client
    assert preview(http, []).json() == []
    (only,) = center_ids(engine, 1)
    assert [center["id"] for center in preview(http, [only]).json()] == [only]
    assert optimizer.calls == []


def test_api_error_is_a_readable_502(client):
    http, engine, optimizer = client

    def fail(_points):
        raise RouteOptimizerError("El módulo de recorridos tardó demasiado en responder.")
    optimizer.answer = fail
    response = preview(http, center_ids(engine, 2))
    assert response.status_code == 502
    assert response.json()["detail"] == "El módulo de recorridos tardó demasiado en responder."


def test_unknown_point_is_a_502_without_inventing_an_order(client):
    http, engine, optimizer = client
    optimizer.answer = lambda points: [points[0], (0.0, 0.0), *points[2:]]
    response = preview(http, center_ids(engine, 3))
    assert response.status_code == 502
    assert "no es de ningún centro" in response.json()["detail"]


def test_answer_with_other_length_or_endpoints_is_a_502(client):
    http, engine, optimizer = client
    ids = center_ids(engine, 3)
    optimizer.answer = lambda points: points[:-1]
    assert preview(http, ids).status_code == 502
    optimizer.answer = lambda points: [points[1], points[0], *points[2:]]
    assert preview(http, ids).status_code == 502


def test_permissions_and_validation(client):
    http, engine, _optimizer = client
    ids = center_ids(engine, 2)
    assert http.post("/api/transport/route-preview", json={"center_ids": ids}).status_code == 401
    assert preview(http, ids, identifier=2).status_code == 403
    assert preview(http, [ids[0], 999999]).status_code == 404
    assert preview(http, [ids[0], ids[0]]).status_code == 422
    with Session(engine) as session:
        session.get(ExtractionCenterModel, ids[1]).active = False
        session.commit()
    assert preview(http, ids).status_code == 404


# Adaptador HTTP con un transporte falso de httpx: no sale a internet.

def client_with(handler):
    return RouteOptimizerClient("https://recorridos.test/api/optimizacion", transport=httpx.MockTransport(handler))


def test_client_sends_contract_body_and_reads_answer():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"coordenadas": [{"lat": 1, "lon": 2}, {"lat": "3.5", "lon": 4}]})
    assert client_with(handler).order([(1.0, 2.0), (3.5, 4.0)]) == [(1.0, 2.0), (3.5, 4.0)]
    assert seen["body"] == {"coordenadas": [{"lat": 1.0, "lon": 2.0}, {"lat": 3.5, "lon": 4.0}]}


@pytest.mark.parametrize("handler", [
    lambda request: httpx.Response(500, text="error"),
    lambda request: httpx.Response(200, text="no es json"),
    lambda request: httpx.Response(200, json={"otra": []}),
])
def test_client_translates_bad_answers(handler):
    with pytest.raises(RouteOptimizerError, match="no respondió correctamente"):
        client_with(handler).order([(1.0, 2.0)])


def test_client_translates_timeout():
    def handler(request):
        raise httpx.ReadTimeout("lento", request=request)
    with pytest.raises(RouteOptimizerError, match="tardó demasiado"):
        client_with(handler).order([(1.0, 2.0)])
