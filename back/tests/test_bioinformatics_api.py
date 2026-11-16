from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_buscar_variantes_apigen_use_case,
    get_database_session,
    get_finalizar_analisis_bioinformatico_use_case,
    get_iniciar_analisis_estudio_use_case,
    get_listar_historial_estudios_use_case,
    get_listar_estudios_bioinformatica_use_case,
    get_obtener_catalogo_patologias_use_case,
    get_obtener_resultado_estudio_use_case,
    get_reenviar_aviso_resultado_use_case,
)
from app.domain.entities.roles import UserRole
from app.infrastructure.database.models import Usuario
from app.infrastructure.database.session import Base
from app.main import app

SECRET = "bioinformatics-api-test-secret-at-least-32-bytes"
STUDY = {
    "id": 8,
    "patient_id": 3,
    "patient_name": "Paciente Demo",
    "patient_dni": "DEMO-3",
    "status": "en_analisis",
    "analyst_id": 1,
    "created_at": datetime(2026, 11, 14, tzinfo=timezone.utc),
    "variantes_detectadas": None,
    "resultado_diagnostico": None,
    "hallazgos_secundarios": None,
    "fecha_reevaluacion": None,
}


class FakeListStudies:
    def execute(self):
        return [STUDY]


class FakeStudyHistory:
    def execute(self, query=""):
        study = {
            **STUDY,
            "status": "resultado_disponible",
            "codigo_patologia": "PERSISTED-CODE",
            "patient": {"email": "stored@example.test"},
            "resultado_diagnostico": "negativo",
        }
        return [study] if not query or query in {"Paciente Demo", "8"} else []


class FakeStartStudy:
    def execute(self, _study_id, _analyst_id):
        return STUDY


class FakeSearchVariants:
    async def execute(self, gen, hgvs_c, limit, offset):
        return {
            "items": [
                {
                    "id": 9,
                    "hgvs_c": "c.1A>G",
                    "proteina": "p.1",
                    "clasificacion": "patogenica",
                }
            ],
            "total": 1,
            "limit": limit,
            "offset": offset,
        }


class FakeFinalizeStudy:
    async def execute(self, **_kwargs):
        return {**STUDY, "status": "resultado_disponible"}


class FakePathologyCatalog:
    async def execute(self):
        return [{"codigo": "FABRY", "nombre": "Enfermedad de Fabry"}]


class FakeStudyResult:
    def execute(self, _study_id, _actor_id, _actor_role):
        return {
            "id": 8,
            "status": "resultado_disponible",
            "patient_name": "Paciente <Demo>",
            "resultado_diagnostico": "negativo",
            "variantes_detectadas": [
                {
                    "gen": "BRCA1",
                    "hgvs_c": "c.1A>G",
                    "clasificacion": "vus",
                }
            ],
            "hallazgos_secundarios": [],
            "fecha_reevaluacion": "2027-11-15",
        }


class FakeResendResultNotification:
    async def execute(self, _study_id):
        return 202


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", SECRET)
    engine = create_engine(f"sqlite:///{tmp_path / 'bioinformatics-api.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for user_id, role in (
            (1, UserRole.BIOINFORMATICIAN),
            (2, UserRole.PATIENT),
            (3, UserRole.SUPER_ADMIN),
        ):
            session.add(
                Usuario(
                    id=user_id,
                    username=f"user{user_id}",
                    email=f"user{user_id}@example.test",
                    role=role,
                    first_name="Demo",
                    last_name="User",
                    phone="000",
                    password_hash="test-hash",
                )
            )
        session.commit()

    def database_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_database_session] = database_session
    app.dependency_overrides[get_listar_estudios_bioinformatica_use_case] = (
        lambda: FakeListStudies()
    )
    app.dependency_overrides[get_listar_historial_estudios_use_case] = (
        lambda: FakeStudyHistory()
    )
    app.dependency_overrides[get_iniciar_analisis_estudio_use_case] = (
        lambda: FakeStartStudy()
    )
    app.dependency_overrides[get_buscar_variantes_apigen_use_case] = (
        lambda: FakeSearchVariants()
    )
    app.dependency_overrides[get_finalizar_analisis_bioinformatico_use_case] = (
        lambda: FakeFinalizeStudy()
    )
    app.dependency_overrides[get_obtener_catalogo_patologias_use_case] = (
        lambda: FakePathologyCatalog()
    )
    app.dependency_overrides[get_obtener_resultado_estudio_use_case] = (
        lambda: FakeStudyResult()
    )
    app.dependency_overrides[get_reenviar_aviso_resultado_use_case] = (
        lambda: FakeResendResultNotification()
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def auth_headers(user_id):
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def test_bioinformatics_routes_only_allow_bioinformatician(api_client):
    headers = auth_headers(1)
    admin_headers = auth_headers(3)

    requests = (
        ("GET", "/api/bioinformatica/estudios", None),
        ("PATCH", "/api/bioinformatica/estudios/8/iniciar", None),
        ("GET", "/api/bioinformatica/variantes?gen=BRCA1", None),
        (
            "POST",
            "/api/bioinformatica/estudios/8/resultados",
            {"codigo_patologia": "BRCA1", "variantes": []},
        ),
        ("POST", "/api/bioinformatica/estudios/8/reenviar-notificacion", None),
    )
    for method, path, body in requests:
        assert api_client.request(method, path).status_code == 401
        assert (
            api_client.request(method, path, headers=auth_headers(2), json=body)
            .status_code
            == 403
        )
        assert (
            api_client.request(method, path, headers=admin_headers, json=body)
            .status_code
            == 403
        )
        assert (
            api_client.request(method, path, headers=headers, json=body).status_code
            != 403
        )


def test_bioinformatics_routes_list_start_search_and_finalize(api_client):
    headers = auth_headers(1)
    assert api_client.patch(
        "/api/bioinformatica/estudios/8/iniciar", headers=headers
    ).json()["status"] == "en_analisis"

    search = api_client.get(
        "/api/bioinformatica/variantes",
        params={"gen": "BRCA1", "hgvs_c": "c.1", "limit": 10, "offset": 5},
        headers=headers,
    )
    assert search.status_code == 200
    assert search.json()["items"][0]["clasificacion"] == "patogenica"

    result = api_client.post(
        "/api/bioinformatica/estudios/8/resultados",
        headers=headers,
        json={
            "codigo_patologia": "BRCA1",
            "variantes": [
                {
                    "id": 9,
                    "gen": "BRCA1",
                    "hgvs_c": "c.1A>G",
                    "proteina": "p.1",
                    "clasificacion": "patogenica",
                }
            ],
        },
    )
    assert result.status_code == 200
    assert result.json()["status"] == "resultado_disponible"


def test_bioinformatics_history_returns_database_studies_and_supports_search(api_client):
    headers = auth_headers(1)

    history = api_client.get("/api/bioinformatica/historial", headers=headers)
    assert history.status_code == 200
    assert history.json()[0]["codigo_patologia"] == "PERSISTED-CODE"
    assert history.json()[0]["patient"]["email"] == "stored@example.test"
    assert history.json()[0]["resultado_diagnostico"] == "negativo"

    filtered = api_client.get(
        "/api/bioinformatica/historial?q=ausente", headers=headers
    )
    assert filtered.status_code == 200
    assert filtered.json() == []

    assert api_client.get("/api/bioinformatica/historial").status_code == 401


def test_bioinformatics_can_resend_result_notification(api_client):
    response = api_client.post(
        "/api/bioinformatica/estudios/8/reenviar-notificacion",
        headers=auth_headers(1),
    )

    assert response.status_code == 200
    assert "reenviado" in response.json()["mensaje"]


def test_pathology_catalog_allows_only_bioinformatician_and_super_admin(api_client):
    path = "/api/bioinformatica/patologias"
    assert api_client.get(path).status_code == 401
    assert api_client.get(path, headers=auth_headers(2)).status_code == 403
    assert api_client.get(path, headers=auth_headers(1)).json() == [
        {"codigo": "FABRY", "nombre": "Enfermedad de Fabry"}
    ]
    assert api_client.get(path, headers=auth_headers(3)).status_code == 200


def test_study_result_can_be_downloaded_as_safe_svg(api_client):
    path = "/api/bioinformatica/estudios/8/resultado.svg"
    assert api_client.get(path).status_code == 401

    response = api_client.get(path, headers=auth_headers(1))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert response.headers["content-disposition"].endswith(
        'filename="estudio-8-resultado.svg"'
    )
    assert "<svg " in response.text
    assert "Paciente &lt;Demo&gt;" in response.text
    assert "BRCA1 - c.1A&gt;G - vus" in response.text
    assert api_client.get(path, headers=auth_headers(2)).status_code == 403
