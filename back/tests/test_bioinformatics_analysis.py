import asyncio
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.domain.entities.roles import UserRole
from app.infrastructure.database.models import Paciente, Usuario
from app.infrastructure.database.session import Base
from app.infrastructure.database.catalog_models import PathologyModel, SymptomModel
from app.infrastructure.database.study_models import StudyModel
from app.infrastructure.external_services.apigen_client import ApigenClient
from app.infrastructure.external_services.errors import ExternalServiceError
from app.infrastructure.external_services.notification_client import NotificationClient
from app.infrastructure.external_services.list_cache import TTLListCache
from app.infrastructure.repositories.sqlalchemy_study_repository import (
    SQLAlchemyStudyRepository,
)
from app.use_cases.analisis_bioinformatico import (
    ProcesarAnalisisUseCase,
    StudyStateConflictError,
)


@pytest.fixture
def factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'bioinformatics.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(engine, expire_on_commit=False)
    engine.dispose()


def create_study(factory, status="en_area_bioinformatica"):
    with factory.begin() as session:
        analyst = Usuario(
            username="bioinformatician",
            role=UserRole.BIOINFORMATICIAN,
            first_name="Bio",
            last_name="Informatician",
            phone="000",
            email="bio@example.test",
            password_hash="test-hash",
        )
        patient = Paciente(
            dni="DEMO-1",
            nombre="Paciente",
            apellido="Demo",
            email="patient@example.test",
        )
        session.add_all([analyst, patient])
        session.flush()
        study = StudyModel(patient_id=patient.id, status=status)
        session.add(study)
        session.flush()
        return study.id, analyst.id


def test_study_claim_is_exclusive_and_persisted(factory):
    study_id, analyst_id = create_study(factory)
    with factory() as first, factory() as second:
        first_repository = SQLAlchemyStudyRepository(first)
        second_repository = SQLAlchemyStudyRepository(second)

        assert first_repository.claim_analysis(study_id, analyst_id)
        assert not second_repository.claim_analysis(study_id, analyst_id)

    with factory() as session:
        study = session.get(StudyModel, study_id)
        assert study.status == "en_analisis"
        assert study.analyst_id == analyst_id


def test_repository_lists_studies_and_persists_bioinformatics_result(factory):
    from datetime import date

    study_id, analyst_id = create_study(factory)
    with factory() as session:
        repository = SQLAlchemyStudyRepository(session)
        assert repository.list_bioinformatics_studies()[0]["id"] == study_id
        assert repository.start_analysis(study_id, analyst_id)
        assert repository.save_bioinformatics_result(
            study_id,
            analyst_id,
            [{"gen": "BRCA1", "hgvs_c": "c.1A>G", "clasificacion": "patogenica"}],
            "positivo",
            [{"gen": "ACMG1"}],
            date(2027, 11, 14),
            "BRCA1",
        )

    with factory() as session:
        study = session.get(StudyModel, study_id)
        assert study.status == "resultado_disponible"
        assert study.resultado_diagnostico == "positivo"
        assert study.fecha_reevaluacion == date(2027, 11, 14)
        assert study.variantes_detectadas[0]["gen"] == "BRCA1"
        assert study.hallazgos_secundarios == [{"gen": "ACMG1"}]
        assert study.codigo_patologia == "BRCA1"


def test_study_repository_returns_patient_data_and_completed_study_history(factory):
    from app.infrastructure.database.patient_clinical_models import (
        PatientClinicalRevision,
    )

    study_id, analyst_id = create_study(factory)
    with factory.begin() as session:
        patient = session.scalar(select(Paciente).where(Paciente.dni == "DEMO-1"))
        physician = Usuario(
            username="treating-physician-history",
            role=UserRole.TREATING_PHYSICIAN,
            first_name="Medica",
            last_name="Tratante",
            phone="000",
            email="physician-history@example.test",
            password_hash="test-hash",
        )
        session.add(physician)
        session.flush()
        patient.created_by_physician_id = physician.id
        patient.clinical_summary = "Resumen persistido en la ficha."
        session.add(
            PatientClinicalRevision(
                patient_id=patient.id,
                version=patient.version,
                changed_by_physician_id=physician.id,
                changed_at=datetime.now(timezone.utc),
                snapshot={
                    "symptoms": [{"id": 1, "name": "Dato registrado"}],
                    "suspicions": [],
                },
            )
        )
        study = session.get(StudyModel, study_id)
        study.status = "resultado_disponible"
        study.analyst_id = analyst_id
        study.codigo_patologia = "CATALOG-CODE"
        study.resultado_diagnostico = "negativo"
        study.variantes_detectadas = [{"gen": "GEN-DB"}]

    with factory() as session:
        repository = SQLAlchemyStudyRepository(session)
        details = repository.bioinformatics_study(study_id)
        history = repository.list_study_history("DEMO-1")
        no_matches = repository.list_study_history("missing")

    assert details["patient"]["clinical_summary"] == "Resumen persistido en la ficha."
    assert details["patient"]["clinical_revision"]["symptoms"][0]["name"] == "Dato registrado"
    assert details["patient"]["physician"]["email"] == "physician-history@example.test"
    assert details["codigo_patologia"] == "CATALOG-CODE"
    assert [item["id"] for item in history] == [study_id]
    assert history[0]["resultado_diagnostico"] == "negativo"
    assert no_matches == []


def test_apigen_uses_expected_paths_headers_and_payload():
    seen = []

    async def responder(request):
        seen.append(request)
        return httpx.Response(
            200,
            json=[] if request.method == "GET" else {"ok": True},
        )

    async def run():
        client = ApigenClient(
            "test-key",
            base_url="https://apigen.test/rest/v1",
            transport=httpx.MockTransport(responder),
        )
        await client.buscar_variantes("BRCA1")
        await client.consultar_diagnostico("P-1", [{"id": "v1"}])
        await client.consultar_hallazgos([{"id": "v1"}], ["P-1"])

    asyncio.run(run())
    assert seen[0].url.path.endswith("/variantes")
    assert seen[0].url.params["gen"] == "eq.BRCA1"
    assert seen[0].headers["apikey"] == "test-key"
    assert seen[1].url.path.endswith("/rpc/resultado_diagnostico")
    assert seen[1].read() == b'{"p_patologia":"P-1","p_variantes":[{"id":"v1"}]}'
    assert seen[2].url.path.endswith("/rpc/hallazgos_secundarios")


def test_apigen_variant_search_sends_filters_pagination_and_count():
    seen = []

    async def responder(request):
        seen.append(request)
        return httpx.Response(
            200,
            headers={"Content-Range": "0-0/17"},
            json=[{"id": 1, "hgvs_c": "c.1A>G", "proteina": "p.1", "clasificacion": "vus"}],
        )

    async def run():
        client = ApigenClient(
            "test-key",
            base_url="https://apigen.test/rest/v1",
            transport=httpx.MockTransport(responder),
        )
        return await client.buscar_variantes("BRCA1", "c.1", 10, 5)

    items, total = asyncio.run(run())
    assert total == 17
    assert items[0]["id"] == 1
    assert seen[0].url.params["select"] == "id,hgvs_c,proteina,clasificacion"
    assert seen[0].url.params["gen"] == "eq.BRCA1"
    assert seen[0].url.params["hgvs_c"] == "ilike.*c.1*"
    assert seen[0].url.params["limit"] == "10"
    assert seen[0].url.params["offset"] == "5"
    assert seen[0].headers["Prefer"] == "count=exact"


def test_apigen_variant_lists_are_cached_by_query_and_copied():
    seen = []

    async def responder(request):
        seen.append(request)
        return httpx.Response(
            200,
            headers={"Content-Range": "0-0/1"},
            json=[
                {
                    "id": 1,
                    "hgvs_c": "c.1A>G",
                    "proteina": "p.1",
                    "clasificacion": "vus",
                }
            ],
        )

    async def run():
        client = ApigenClient(
            "test-key",
            base_url="https://apigen.test/rest/v1",
            transport=httpx.MockTransport(responder),
            list_cache=TTLListCache(ttl_seconds=600),
        )
        first = await client.buscar_variantes("BRCA1")
        first[0][0]["clasificacion"] = "modified-by-caller"
        second = await client.buscar_variantes("BRCA1")
        third = await client.buscar_variantes("BRCA2")
        return second, third

    second, third = asyncio.run(run())
    assert second[0][0]["clasificacion"] == "vus"
    assert second[1] == third[1] == 1
    assert len(seen) == 2


def test_ttl_list_cache_expires_entries(monkeypatch):
    import app.infrastructure.external_services.list_cache as cache_module

    now = [100.0]
    monkeypatch.setattr(cache_module, "monotonic", lambda: now[0])
    cache = TTLListCache(ttl_seconds=600)
    cache.set("key", [{"id": 1}])
    assert cache.get("key") == [{"id": 1}]

    now[0] = 700.0
    assert cache.get("key") is None


@pytest.mark.parametrize("status", [400, 401, 422, 500])
def test_apigen_translates_upstream_errors_with_same_status(status):
    async def responder(_request):
        return httpx.Response(status, json={"message": "invalid variant"})

    async def run():
        client = ApigenClient(
            "test-key",
            base_url="https://apigen.test/rest/v1",
            transport=httpx.MockTransport(responder),
        )
        with pytest.raises(ExternalServiceError, match="invalid variant") as error:
            await client.consultar_diagnostico("P-1", [])
        assert error.value.status_code == status

    asyncio.run(run())


def test_apigen_timeout_is_reported_as_service_unavailable():
    async def responder(_request):
        raise httpx.ReadTimeout("upstream timed out")

    async def run():
        client = ApigenClient(
            "test-key",
            base_url="https://apigen.test/rest/v1",
            transport=httpx.MockTransport(responder),
        )
        with pytest.raises(ExternalServiceError) as error:
            await client.consultar_diagnostico("P-1", [])
        assert error.value.status_code == 503

    asyncio.run(run())


def test_apigen_configuration_accepts_current_and_canonical_key_names():
    from app.config import Settings

    canonical = Settings(
        _env_file=None,
        APIGEN_API_KEY="publishable-test",
        APIGEN_BASE_URL="https://apigen.example/rest/v1",
    )
    legacy = Settings(
        _env_file=None,
        API_SECRET_KEY_API_GEN="supabase-secret-test",
        API_GEN_URL="https://apigen-legacy.example/rest/v1",
    )
    url_alias = Settings(_env_file=None, API_GEN_URL="https://apigen.example/rest/v1")
    assert canonical.apigen_api_key.get_secret_value() == "publishable-test"
    assert legacy.apigen_api_key.get_secret_value() == "supabase-secret-test"
    assert url_alias.apigen_base_url == "https://apigen.example/rest/v1"
    assert canonical.apigen_base_url == "https://apigen.example/rest/v1"


def test_apigen_configuration_requires_base_url(monkeypatch):
    import app.config as config

    monkeypatch.setattr(config, "get_settings", lambda: config.Settings(_env_file=None))
    with pytest.raises(RuntimeError, match="API_GEN_URL"):
        config.get_apigen_base_url()


def test_notification_uses_idempotency_and_logs_accepted(caplog):
    caplog.set_level("INFO")
    seen = []

    async def responder(request):
        seen.append(request)
        return httpx.Response(
            202,
            json={
                "id": "00000000-0000-4000-8000-000000000012",
                "estado": "pendiente",
                "creado": True,
            },
        )

    async def run():
        client = NotificationClient(
            "notification-test-key", transport=httpx.MockTransport(responder)
        )
        await client.enviar_aviso_resultado(
            12,
            "Resultado",
            "Listo",
            [{"canal": "email", "destino": "patient@example.test"}],
        )

    asyncio.run(run())
    assert seen[0].url.path.endswith("/avisos")
    assert seen[0].headers["X-API-Key"] == "notification-test-key"
    assert seen[0].headers["Idempotency-Key"] == "resultado-12-aviso"
    assert b'"referencia":"12"' in seen[0].read()
    assert "Result notification accepted for study 12" in caplog.text


@pytest.mark.parametrize("status", [400, 401, 409])
def test_notification_surfaces_client_errors(status):
    async def responder(_request):
        return httpx.Response(status, json={"error": "notification rejected"})

    async def run():
        client = NotificationClient(
            "notification-test-key", transport=httpx.MockTransport(responder)
        )
        with pytest.raises(ExternalServiceError, match="notification rejected"):
            await client.enviar_aviso_resultado(
                12,
                "Asunto",
                "Mensaje",
                [{"canal": "email", "destino": "patient@example.test"}],
            )

    asyncio.run(run())


def test_notification_accepts_idempotent_duplicate():
    async def responder(_request):
        return httpx.Response(
            200,
            json={
                "id": "00000000-0000-4000-8000-000000000012",
                "estado": "pendiente",
                "creado": False,
            },
        )

    async def run():
        client = NotificationClient(
            "notification-test-key", transport=httpx.MockTransport(responder)
        )
        return await client.enviar_aviso_resultado(
            12,
            "Asunto",
            "Mensaje",
            [{"canal": "email", "destino": "patient@example.test"}],
        )

    assert asyncio.run(run()) == 200


class FakeStudyRepository:
    def __init__(self):
        self.current_status = "en_area_bioinformatica"
        self.claimed = False
        self.saved = None
        self.released = False

    def status(self, _study_id):
        return self.current_status

    def notification_recipients(self, _study_id):
        return [
            {"canal": "email", "destino": "patient@example.test"},
            {"canal": "email", "destino": "physician@example.test"},
        ]

    def physician_owns_study(self, _study_id, physician_id):
        return physician_id == 7

    def claim_analysis(self, _study_id, _analyst_id):
        if self.claimed:
            return False
        self.claimed = True
        self.current_status = "en_analisis"
        return True

    def release_analysis(self, _study_id, _analyst_id):
        self.released = True
        self.current_status = "en_area_bioinformatica"
        return True

    def complete_analysis(self, _study_id, _analyst_id, result):
        self.saved = result
        self.current_status = "resultado_disponible"
        return True

    def result_for_analyst(self, _study_id, _analyst_id):
        return self.saved if self.current_status == "resultado_disponible" else None

    def list_bioinformatics_studies(self):
        return []

    def start_analysis(self, _study_id, analyst_id):
        if self.claimed:
            return False
        self.claimed = True
        self.current_status = "en_analisis"
        self.owner = analyst_id
        return True

    def claim_unassigned_analysis(self, _study_id, analyst_id):
        owner = getattr(self, "owner", None)
        if owner is None:
            self.owner = analyst_id
            return True
        return owner == analyst_id

    def analysis_owner(self, _study_id):
        return getattr(self, "owner", None)

    def bioinformatics_study(self, study_id):
        if self.current_status == "resultado_disponible":
            result = self.saved or {}
            return {"id": study_id, "status": self.current_status, **result}
        return {"id": study_id, "status": self.current_status}

    def save_bioinformatics_result(
        self,
        study_id,
        analyst_id,
        variantes_detectadas,
        resultado_diagnostico,
        hallazgos_secundarios,
        fecha_reevaluacion,
        codigo_patologia,
    ):
        self.current_status = "resultado_disponible"
        self.owner = analyst_id
        self.saved = {
            "id": study_id,
            "variantes_detectadas": variantes_detectadas,
            "resultado_diagnostico": resultado_diagnostico,
            "hallazgos_secundarios": hallazgos_secundarios,
            "fecha_reevaluacion": fecha_reevaluacion,
            "codigo_patologia": codigo_patologia,
        }
        return True


class FakeApigen:
    async def consultar_diagnostico(self, _pathology, _variants):
        return {"diagnosis": "demo"}

    async def consultar_hallazgos(self, _variants, _excluded):
        return [{"finding": "demo"}]

    async def resultado_diagnostico(self, _pathology, _variants):
        return "positivo"

    async def hallazgos_secundarios(self, _variants, _excluded):
        return [{"finding": "demo"}]

    async def buscar_variantes(self, _gen, _hgvs_c, _limit, _offset):
        return [{"id": 1}], 1


class FakeNotifications:
    def __init__(self):
        self.calls = []

    async def enviar_aviso_resultado(self, **kwargs):
        self.calls.append(kwargs)
        return 202


class FakeResultNotifications:
    def __init__(self):
        self.calls = []

    async def enviar_aviso_resultado(self, **kwargs):
        self.calls.append(kwargs)
        return 202


def test_analysis_persists_result_notifies_and_retries_notification_only():
    repository = FakeStudyRepository()
    notifications = FakeNotifications()
    use_case = ProcesarAnalisisUseCase(repository, FakeApigen(), notifications)

    async def run():
        result = await use_case.execute(12, 4, "P-1", [{"id": "v1"}])
        retry = await use_case.execute(12, 4, "P-1", [{"id": "v1"}])
        return result, retry

    result, retry = asyncio.run(run())
    assert result == retry == repository.saved
    assert repository.current_status == "resultado_disponible"
    assert len(notifications.calls) == 2
    assert notifications.calls[0]["mensaje"] == (
        "Tu resultado está listo para ser consultado en la web"
    )


def test_analysis_rejects_study_already_claimed():
    repository = FakeStudyRepository()
    repository.claimed = True
    use_case = ProcesarAnalisisUseCase(repository, FakeApigen(), FakeNotifications())

    async def run():
        await use_case.execute(12, 4, "P-1", [{"id": "v1"}])

    with pytest.raises(StudyStateConflictError):
        asyncio.run(run())


def test_bioinformatics_finalizer_maps_variants_and_schedules_reassessment(monkeypatch):
    from datetime import date as real_date

    from app.use_cases.bioinformatics import FinalizarAnalisisBioinformaticoUseCase

    class FixedDate(real_date):
        @classmethod
        def today(cls):
            return cls(2026, 11, 14)

    monkeypatch.setattr("app.use_cases.bioinformatics.date", FixedDate)
    repository = FakeStudyRepository()
    apigen = FakeApigen()
    notifications = FakeResultNotifications()
    use_case = FinalizarAnalisisBioinformaticoUseCase(
        repository, apigen, notifications
    )
    variants = [
        {
            "gen": "BRCA1",
            "hgvs_c": "c.1A>G",
            "proteina": "p.1",
            "clasificacion": "probablemente_patogenica",
        }
    ]

    result = asyncio.run(use_case.execute(10, 4, "BRCA1", variants))

    assert result["status"] == "resultado_disponible"
    assert result["resultado_diagnostico"] == "negativo"
    assert result["fecha_reevaluacion"] == FixedDate(2027, 11, 14)
    assert repository.saved["variantes_detectadas"] == variants
    assert len(notifications.calls) == 1
    assert len(notifications.calls[0]["destinatarios"]) == 2
    assert notifications.calls[0]["study_id"] == 10
    assert "variantes" not in notifications.calls[0]["mensaje"]


def test_bioinformatics_finalizer_only_accepts_positive_with_pathogenic_variant():
    from app.use_cases.bioinformatics import FinalizarAnalisisBioinformaticoUseCase

    repository = FakeStudyRepository()
    notifications = FakeResultNotifications()
    result = asyncio.run(
        FinalizarAnalisisBioinformaticoUseCase(
            repository, FakeApigen(), notifications
        ).execute(
            10,
            4,
            "BRCA1",
            [
                {
                    "gen": "BRCA1",
                    "hgvs_c": "c.1A>G",
                    "proteina": None,
                    "clasificacion": "patogenica",
                }
            ],
        )
    )
    assert result["resultado_diagnostico"] == "positivo"
    assert result["fecha_reevaluacion"] is None
    assert len(notifications.calls) == 1


def test_bioinformatics_finalizer_retries_only_notification_with_same_generic_content():
    from app.use_cases.bioinformatics import FinalizarAnalisisBioinformaticoUseCase

    repository = FakeStudyRepository()
    notifications = FakeResultNotifications()
    use_case = FinalizarAnalisisBioinformaticoUseCase(
        repository, FakeApigen(), notifications
    )
    variants = [
        {
            "gen": "BRCA1",
            "hgvs_c": "c.1A>G",
            "proteina": None,
            "clasificacion": "patogenica",
        }
    ]

    async def run():
        await use_case.execute(10, 4, "BRCA1", variants)
        return await use_case.execute(10, 4, "BRCA1", variants)

    result = asyncio.run(run())
    assert result["status"] == "resultado_disponible"
    assert len(notifications.calls) == 2
    assert notifications.calls[0] == notifications.calls[1]


def test_resend_result_notification_uses_a_new_idempotency_key_without_result_data():
    from app.use_cases.bioinformatics import ReenviarAvisoResultadoUseCase

    repository = FakeStudyRepository()
    repository.current_status = "resultado_disponible"
    notifications = FakeResultNotifications()

    asyncio.run(
        ReenviarAvisoResultadoUseCase(repository, notifications).execute(10)
    )

    assert len(notifications.calls) == 1
    assert notifications.calls[0]["idempotency_key"].startswith(
        "resultado-10-reenvio-"
    )
    assert len(notifications.calls[0]["destinatarios"]) == 2
    assert "variantes" not in notifications.calls[0]["mensaje"]


def test_resend_result_notification_requires_published_study():
    from app.use_cases.bioinformatics import (
        BioinformaticsStudyConflictError,
        ReenviarAvisoResultadoUseCase,
    )

    repository = FakeStudyRepository()
    notifications = FakeResultNotifications()

    with pytest.raises(BioinformaticsStudyConflictError):
        asyncio.run(
            ReenviarAvisoResultadoUseCase(repository, notifications).execute(10)
        )

    assert notifications.calls == []


def test_study_result_access_is_limited_to_assigned_analyst_and_attending_physician():
    from app.domain.entities.roles import UserRole
    from app.use_cases.bioinformatics import (
        BioinformaticsStudyNotFoundError,
        ObtenerResultadoEstudioUseCase,
    )

    repository = FakeStudyRepository()
    repository.current_status = "resultado_disponible"
    repository.owner = 4
    repository.saved = {"resultado_diagnostico": "negativo"}
    use_case = ObtenerResultadoEstudioUseCase(repository)

    assert (
        use_case.execute(10, 4, UserRole.BIOINFORMATICIAN)["status"]
        == "resultado_disponible"
    )
    assert (
        use_case.execute(10, 7, UserRole.TREATING_PHYSICIAN)["status"]
        == "resultado_disponible"
    )
    with pytest.raises(BioinformaticsStudyNotFoundError):
        use_case.execute(10, 8, UserRole.TREATING_PHYSICIAN)
    with pytest.raises(BioinformaticsStudyNotFoundError):
        use_case.execute(10, 9, UserRole.BIOINFORMATICIAN)
