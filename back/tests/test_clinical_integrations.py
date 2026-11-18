import asyncio
import json
import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.infrastructure.external_services.apigen_client import ApigenClient
from app.infrastructure.external_services.cdss_client import CDSSClient
from app.infrastructure.external_services.errors import ExternalServiceError
from app.infrastructure.database.session import Base
from app.infrastructure.database.catalog_models import SymptomModel
from app.infrastructure.repositories.sqlalchemy_pathology_repository import SQLAlchemyPathologyRepository
from app.use_cases.pathologies import PathologyCatalog


def test_apigen_catalog_group_and_full_payload():
    payload = [{"codigo": "MPS1", "nombre": "MPS I", "genes": ["IDUA"], "herencia": "autosomica_recesiva", "de_grupo": False}]
    def respond(request):
        assert request.url.path == "/rest/v1/rpc/listar_patologias"
        assert json.loads(request.content) == {"p_grupo_id": "grupo6"}
        return httpx.Response(200, json=payload)
    client = ApigenClient("test", base_url="https://example.test/rest/v1", transport=httpx.MockTransport(respond))
    assert asyncio.run(client.listar_patologias_grupo("grupo6")) == payload


def test_cdss_full_catalog_and_advice_contract():
    symptom = {"snomed_codigo": "247398009", "termino": "Dolor", "es_cardinal": True}
    payload = [{"codigo": "FABRY", "nombre": "Fabry", "sintomas": [symptom]}]
    advice = {"compatible": False, "estrategia": "MENOR_DIFERENCIA", "patologias": [], "ranking": [], "mensaje": "Sin cardinales"}
    def respond(request):
        if request.method == "GET":
            return httpx.Response(200, json=payload)
        assert json.loads(request.content) == {"sintomas": ["247398009"]}
        return httpx.Response(200, json=advice)
    client = CDSSClient("test", transport=httpx.MockTransport(respond))
    assert asyncio.run(client.obtener_catalogo_completo()) == payload
    assert asyncio.run(client.sugerir(["247398009"])) == advice


def test_external_link_preserves_local_rule_and_survives_edit(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'mapping.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(SymptomModel(id=1, code="DEMO-1", label="Demo", code_system="DEMO"))
        session.commit()
        repo = SQLAlchemyPathologyRepository(session)
        catalog = PathologyCatalog(repo)
        saved = catalog.save("Local", 1, [])
        linked = repo.link_external(saved.id, "FABRY", "", "FABRY")
        assert linked.id == saved.id
        assert linked.cardinal_symptom.id == 1
        assert linked.name == "Local"
        edited = catalog.save("Nuevo nombre local", 1, [], saved.id)
        assert edited.apigen_code == "FABRY"
        assert edited.cdss_code == "FABRY"
        second = catalog.save("Otra", 1, [])
        with pytest.raises(ValueError):
            repo.link_external(second.id, "FABRY", "", None)
    engine.dispose()


@pytest.fixture
def clinical_api(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.routes.clinical_integrations import router
    from app.api.catalog_dependencies import get_catalog, get_current_user
    from app.api.routes.clinical_integrations import get_apigen_client, get_cdss_client
    from app.domain.entities.user import AuthenticatedUser
    from app.domain.entities.roles import UserRole
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add_all([SymptomModel(id=1, code="247398009", label="Dolor guardado", code_system="SNOMED"), SymptomModel(id=2, code="DEMO-2", label="Demo", code_system="DEMO")])
    session.commit()
    catalog = PathologyCatalog(SQLAlchemyPathologyRepository(session))
    catalog.save("Nombre local", 2, [])
    class Genetic:
        created = []
        async def listar_patologias_grupo(self, group):
            assert group == "grupo6"
            return [{"codigo": "FABRY", "nombre": "Fabry", "genes": ["GLA"], "herencia": "ligada_al_x", "de_grupo": False}]
        async def alta_patologia(self, *args):
            self.created.append(args)
            raise ExternalServiceError("Apigen", "secret-do-not-echo", 503)
    class Clinical:
        calls = []
        async def obtener_catalogo_completo(self):
            return [{"codigo": "FABRY", "nombre": "Fabry", "sintomas": [{"snomed_codigo": "247398009", "termino": "Nuevo texto externo", "es_cardinal": True}, {"snomed_codigo": "29738008", "termino": "Otro", "es_cardinal": True}]}]
        async def sugerir(self, codes):
            self.calls.append(codes)
            return {"compatible": False, "estrategia": "MENOR_DIFERENCIA", "patologias": [], "ranking": [], "mensaje": None}
    app = FastAPI()
    app.include_router(router)
    genetic, clinical = Genetic(), Clinical()
    actor = [AuthenticatedUser(1, "synthetic@example.test", UserRole.MEDICAL_MANAGER)]
    app.dependency_overrides[get_current_user] = lambda: actor[0]
    app.dependency_overrides[get_catalog] = lambda: catalog
    app.dependency_overrides[get_apigen_client] = lambda: genetic
    app.dependency_overrides[get_cdss_client] = lambda: clinical
    with TestClient(app) as client:
        yield client, catalog, genetic, clinical, actor
    session.close()
    engine.dispose()


def test_advice_only_sends_stored_snomed_and_does_not_reject_local_suspicion(clinical_api):
    client, catalog, _, clinical, _ = clinical_api
    response = client.post("/api/clinical-integrations/cdss/advice", json={"symptom_ids": [1, 2, 1]})
    assert response.status_code == 200
    assert response.json()["excluded_symptom_ids"] == [2]
    assert clinical.calls == [["247398009"]]
    assert response.json()["result"]["compatible"] is False
    assert catalog.validate(1, [2]).valid
    assert client.post("/api/clinical-integrations/cdss/advice", json={"symptom_ids": [2]}).status_code == 422
    assert client.post("/api/clinical-integrations/cdss/advice", json={"symptom_ids": [999]}).status_code == 422
    assert len(clinical.calls) == 1


def test_link_verifies_code_and_preserves_rules(clinical_api):
    client, catalog, *_ = clinical_api
    url = "/api/clinical-integrations/pathologies/1/identity"
    assert client.put(url, json={"apigen_code": "made-up"}).status_code == 422
    result = client.put(url, json={"apigen_code": "FABRY", "cdss_code": "FABRY"})
    assert result.status_code == 200
    assert result.json()["id"] == 1
    assert result.json()["cardinal_symptom"]["id"] == 2
    assert catalog.get(1).name == "Nombre local"
    assert client.put(url, json={"apigen_code": "FABRY"}).status_code == 422


def test_draft_preserves_existing_term_and_requires_separate_pathology_save(clinical_api):
    client, catalog, *_ = clinical_api
    url = "/api/clinical-integrations/cdss/pathologies/FABRY/draft"
    first = client.post(url)
    assert first.status_code == 200
    assert len(first.json()["cardinals"]) == 2
    assert first.json()["cardinals"][0]["label"] == "Dolor guardado"
    assert client.post(url).json() == first.json()
    assert catalog.get(1).cardinal_symptom.id == 2
    assert catalog.get(1).apigen_code is None


def test_remote_creation_requires_explicit_confirmation_and_recovers_uncertain_result(clinical_api):
    client, catalog, genetic, *_ = clinical_api
    body = {"codigo": "NEW", "nombre": "Synthetic", "genes": ["GLA"], "herencia": "ligada_al_x"}
    url = "/api/clinical-integrations/apigen/pathologies"
    assert client.post(url, json=body).status_code == 422
    assert not genetic.created
    assert client.post(url, json=body | {"codigo": "FABRY", "confirm_remote_write": True}).status_code == 409
    assert not genetic.created
    result = client.post(url, json=body | {"confirm_remote_write": True})
    assert result.status_code == 502
    assert "Actualizá" in result.json()["detail"]
    assert "secret" not in result.text
    assert catalog.get(1).apigen_code is None


def test_clinical_permissions(clinical_api):
    from app.domain.entities.user import AuthenticatedUser
    from app.domain.entities.roles import UserRole
    client, _, _, _, actor = clinical_api
    actor[0] = AuthenticatedUser(1, "synthetic@example.test", UserRole.TREATING_PHYSICIAN)
    assert client.get("/api/clinical-integrations/cdss/pathologies").status_code == 200
    assert client.post("/api/clinical-integrations/cdss/pathologies/FABRY/draft").status_code == 403
    assert client.put("/api/clinical-integrations/pathologies/1/identity", json={"apigen_code": "FABRY"}).status_code == 403
    actor[0] = AuthenticatedUser(1, "synthetic@example.test", UserRole.SUPER_ADMIN)
    assert client.get("/api/clinical-integrations/apigen/pathologies").status_code == 403


@pytest.mark.parametrize("payload", [None, {}, [{"codigo": "FABRY"}]])
def test_cdss_rejects_malformed_full_catalog(payload):
    client = CDSSClient("test", transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload)))
    with pytest.raises(ExternalServiceError):
        asyncio.run(client.obtener_catalogo_completo())


@pytest.mark.parametrize("provider", ["apigen", "cdss"])
def test_missing_provider_configuration_is_503(monkeypatch, provider):
    from fastapi import HTTPException
    from app.api.routes import clinical_integrations as routes
    def unavailable():
        raise RuntimeError("secret-config-details")
    monkeypatch.setattr(routes, f"shared_{provider}_client", unavailable)
    with pytest.raises(HTTPException) as failure:
        getattr(routes, f"get_{provider}_client")()
    assert failure.value.status_code == 503
    assert "secret" not in failure.value.detail


def test_stale_session_cannot_replace_mapping(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'race.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as setup:
        setup.add(SymptomModel(id=1, code="DEMO-1", label="Demo", code_system="DEMO"))
        setup.commit()
        PathologyCatalog(SQLAlchemyPathologyRepository(setup)).save("Local", 1, [])
    with Session(engine) as first, Session(engine) as second:
        from app.infrastructure.database.catalog_models import PathologyModel
        stale = second.get(PathologyModel, 1)
        assert stale.apigen_code is None
        SQLAlchemyPathologyRepository(first).link_external(1, "FABRY", "", None)
        with pytest.raises(ValueError):
            SQLAlchemyPathologyRepository(second).link_external(1, "POMPE", "", None)
        assert SQLAlchemyPathologyRepository(first).get_pathology(1).apigen_code == "FABRY"
    engine.dispose()


def test_cdss_clinical_timeout_is_bounded_and_explained():
    def respond(request):
        assert request.extensions["timeout"]["read"] == 60
        raise httpx.ReadTimeout("private network detail", request=request)
    client = CDSSClient("secret", transport=httpx.MockTransport(respond))
    with pytest.raises(ExternalServiceError, match="tardó demasiado") as failure:
        asyncio.run(client.sugerir(["29857009"]))
    assert failure.value.status_code == 503
    assert "private" not in str(failure.value)
