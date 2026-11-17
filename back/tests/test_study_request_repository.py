"""Repositorio SQLAlchemy de solicitudes, pagos y cupones sobre una base SQLite temporal."""

import asyncio

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from study_request_fakes import FakeCoupons, FakeGeneCatalog, FakeInsurance

from app.domain.entities.roles import UserRole
from app.domain.entities.study_request import GeneRef, PathologyRef
from app.domain.entities.user import AuthenticatedUser
from app.domain.interfaces.study_request_repository import DuplicateOperationError
from app.infrastructure.database import (  # noqa: F401
    catalog_models,
    family_models,
    logistics_models,
    models,
    patient_clinical_models,
    study_models,
)
from app.infrastructure.database.models import Paciente, Usuario
from app.infrastructure.database.session import Base
from app.infrastructure.database.study_models import StudyModel
from app.infrastructure.repositories.sqlalchemy_study_request_repository import (
    SqlAlchemyStudyRequestRepository,
)
from app.use_cases.coupons import CouponService
from app.use_cases.study_payments import StudyPaymentService
from app.use_cases.study_request_errors import StudyRequestConflictError
from app.use_cases.study_requests import StudyRequestService


def run(coro):
    return asyncio.run(coro)


def make_user(user_id, role):
    return Usuario(
        id=user_id, username=f"demo{user_id}", role=role, first_name="Demo", last_name=f"Prueba{user_id}",
        phone="000", email=f"demo{user_id}@example.test", password_hash="not-a-real-password",
        specialty="Genética médica" if role is UserRole.TREATING_PHYSICIAN else None,
        license_number="MN-DEMO" if role is UserRole.TREATING_PHYSICIAN else None,
    )


PHYSICIAN = AuthenticatedUser(10, "demo10@example.test", UserRole.TREATING_PHYSICIAN)
ADMIN = AuthenticatedUser(20, "demo20@example.test", UserRole.LAB_ADMINISTRATOR)
PATIENT = AuthenticatedUser(40, "demo40@example.test", UserRole.PATIENT)


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'requests.db'}")

    @event.listens_for(engine, "connect")
    def _foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                make_user(10, UserRole.TREATING_PHYSICIAN),
                make_user(11, UserRole.TREATING_PHYSICIAN),
                make_user(20, UserRole.LAB_ADMINISTRATOR),
                make_user(40, UserRole.PATIENT),
            ]
        )
        session.flush()
        session.add(Paciente(id=1, dni="45000001", nombre="Paciente", apellido="DEMO", usuario_id=40))
        session.commit()
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    with Session(engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
def repo(session):
    return SqlAlchemyStudyRequestRepository(session)


def new_study(repo, genes=(("GLA", "catalogo"),)):
    return repo.create_study(
        patient_id=1,
        physician_id=10,
        include_secondary_findings=False,
        pathologies=[PathologyRef("FABRY", "Enfermedad de Fabry")],
        genes=[GeneRef(symbol, origin) for symbol, origin in genes],
    )


def test_people_lookups(repo):
    assert repo.patient_exists(1) and not repo.patient_exists(2)
    assert repo.patient_id_for_user(40) == 1 and repo.patient_id_for_user(10) is None
    assert repo.patient_full_name(1) == "Paciente DEMO"
    assert repo.physician_exists(10) and not repo.physician_exists(20) and not repo.physician_exists(999)
    assert [p["id"] for p in repo.list_physicians()] == [10, 11]


def test_study_is_created_with_pathologies_and_genes_in_order(repo):
    study = new_study(repo, genes=(("GLA", "catalogo"), ("BRCA1", "manual")))
    repo.commit()
    loaded = repo.get_study(study.id)
    assert (loaded.status, loaded.physician_id, loaded.patient_id) == ("creado", 10, 1)
    assert [(g.symbol, g.origin) for g in loaded.genes] == [("GLA", "catalogo"), ("BRCA1", "manual")]
    assert [p.code for p in loaded.pathologies] == ["FABRY"]
    assert loaded.include_secondary_findings is False


def test_database_rejects_duplicate_genes_in_a_study(repo):
    with pytest.raises(IntegrityError):
        new_study(repo, genes=(("GLA", "catalogo"), ("GLA", "manual")))


def test_list_studies_filters_and_skips_legacy_rows_without_physician(repo, session):
    mine = new_study(repo)
    session.add(StudyModel(patient_id=1, status="pagado"))  # estudio previo, sin médico solicitante
    repo.commit()
    assert [s.id for s in repo.list_studies()] == [mine.id]
    assert [s.id for s in repo.list_studies(physician_id=10)] == [mine.id]
    assert repo.list_studies(physician_id=11) == []
    assert [s.id for s in repo.list_studies(patient_id=1)] == [mine.id]


def test_transition_status_is_conditional(repo):
    study = new_study(repo)
    repo.commit()
    assert repo.transition_status(study.id, "creado", "pendiente_pago") is True
    assert repo.transition_status(study.id, "creado", "pagado") is False
    assert repo.get_study(study.id).status == "pendiente_pago"


def test_budget_and_updates(repo):
    study = new_study(repo)
    budget = repo.create_budget(
        study_id=study.id, gene_count=1, base_cents=50000, extra_genes=0, extra_cents=0,
        total_cents=50000, currency="USD", issued_by_user_id=20,
    )
    repo.update_budget(budget.id, payment_mode="obra_social", coverage_percent=40.0, insurer_cents=20000, patient_cents=30000)
    repo.commit()
    loaded = repo.get_budget(study.id)
    assert (loaded.payment_mode, loaded.coverage_percent, loaded.insurer_cents, loaded.patient_cents) == ("obra_social", 40.0, 20000, 30000)
    with pytest.raises(ValueError):
        repo.update_budget(budget.id, total_cents=1)
    with pytest.raises(IntegrityError):  # un solo presupuesto por estudio
        repo.create_budget(
            study_id=study.id, gene_count=1, base_cents=1, extra_genes=0, extra_cents=0,
            total_cents=1, currency="USD", issued_by_user_id=20,
        )


def test_operation_uniqueness_and_rollback(repo):
    study = new_study(repo)
    budget = repo.create_budget(
        study_id=study.id, gene_count=1, base_cents=50000, extra_genes=0, extra_cents=0,
        total_cents=50000, currency="USD", issued_by_user_id=20,
    )
    repo.commit()
    args = dict(study_id=study.id, budget_id=budget.id, patient_id=1, op_type="cobro_paciente",
                status="registrando", amount_cents=50000, currency="USD")
    operation_id = repo.register_operation(**args)
    with pytest.raises(DuplicateOperationError):
        repo.register_operation(**args)
    repo.rollback()
    assert repo.list_operations(study.id) == []  # nada se había confirmado

    operation_id = repo.register_operation(**args)
    repo.commit()
    repo.update_operation(operation_id, status="registrada")
    repo.commit()
    assert repo.list_operations(study.id)[0]["status"] == "registrada"
    with pytest.raises(DuplicateOperationError):
        repo.register_operation(**args)
    repo.rollback()
    repo.delete_operation(operation_id)
    repo.commit()
    assert repo.list_operations(study.id) == []


def test_coupon_state_machine_is_atomic(repo):
    repo.add_coupons([("1111", 15.0)])
    repo.commit()
    assert repo.get_coupon("1111").status == "disponible"
    assert repo.assign_coupon_to_patient("1111", 10, 1) is False  # todavía no es del médico
    assert repo.assign_coupon_to_medico("1111", 10) is True
    assert repo.assign_coupon_to_medico("1111", 11) is False
    assert repo.assign_coupon_to_patient("1111", 11, 1) is False  # otro médico
    assert repo.assign_coupon_to_patient("1111", 10, 1) is True
    assert repo.claim_coupon("1111", 2) is False  # otro paciente
    assert repo.claim_coupon("1111", 1) is True
    assert repo.claim_coupon("1111", 1) is False  # solo gana un pedido
    assert repo.release_coupon("1111", 1) is True
    assert repo.claim_coupon("1111", 1) is True
    assert repo.mark_coupon_used("1111", None) is True
    assert repo.mark_coupon_used("1111", None) is False
    repo.commit()
    used = repo.get_coupon("1111")
    assert (used.status, used.medico_id, used.patient_id, used.percentage) == ("usado", 10, 1, 15.0)
    assert [c.code for c in repo.list_coupons(status="usado", medico_id=10, patient_id=1)] == ["1111"]
    assert repo.list_coupons(status="disponible") == []


def test_end_to_end_with_real_repository_persists_each_stage(engine):
    gateway = FakeCoupons()
    with Session(engine, expire_on_commit=False) as s:
        repo = SqlAlchemyStudyRequestRepository(s)
        requests = StudyRequestService(repo, FakeGeneCatalog())
        payments = StudyPaymentService(repo, FakeInsurance(), gateway)
        coupons = CouponService(repo, gateway, "G-TEST")

        study_id = run(requests.crear(physician_id=10, patient_id=1, pathology_codes=["FABRY"], additional_genes=["BRCA1"]))["id"]
        requests.emitir_presupuesto(study_id, ADMIN)
        run(payments.elegir_modalidad(study_id, PATIENT, "obra_social", "os-1"))
        run(payments.autorizar_cobertura(study_id, ADMIN))
        code = run(coupons.generar_lote(1, 20))[0]["code"]
        run(coupons.asignar_a_medico(code, 10))
        run(coupons.asignar_a_paciente(code, PHYSICIAN, 1))
        detail = run(payments.pagar(study_id, PATIENT, code))
        assert detail["status"] == "autorizado"

        with pytest.raises(StudyRequestConflictError):
            run(payments.pagar(study_id, PATIENT))

    with Session(engine) as fresh:  # lo confirmado sobrevive a la sesión
        repo = SqlAlchemyStudyRequestRepository(fresh)
        assert repo.get_study(study_id).status == "autorizado"
        operations = {op["type"]: op for op in repo.list_operations(study_id)}
        assert operations["cobertura_obra_social"]["amount_cents"] == 20000
        assert operations["cobro_paciente"]["amount_cents"] == 24000
        assert operations["cobro_paciente"]["discount_cents"] == 6000
        assert repo.get_coupon(code).status == "usado"
        coverage = repo.get_coverage_request(study_id)
        assert coverage.status == "autorizada" and coverage.authorize_url.endswith("/autorizar")
