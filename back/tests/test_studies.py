import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker

from app.infrastructure.database.models import Paciente
from app.infrastructure.database.seed_demo_studies import seed_demo_studies
from app.infrastructure.database.session import Base
from app.infrastructure.database.study_models import StudyModel
from app.infrastructure.repositories.sqlalchemy_study_repository import SQLAlchemyStudyRepository
from app.use_cases.studies import StudyService


@pytest.fixture
def factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'studies.db'}")
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    yield sessionmaker(engine, expire_on_commit=False)
    engine.dispose()


def add_patient(factory, dni="45000001"):
    with factory.begin() as session:
        patient = Paciente(dni=dni, nombre="Sofía", apellido="DEMO")
        session.add(patient)
    return patient.id


def add_study(factory, status):
    patient_id = add_patient(factory, dni=f"DEMO-{status}")
    with factory.begin() as session:
        study = StudyModel(patient_id=patient_id, status=status)
        session.add(study)
    return study.id


def service(session):
    return StudyService(SQLAlchemyStudyRepository(session))


@pytest.mark.parametrize("status, enabled", [
    ("pagado", True), ("autorizado", True), ("requiere_remuestreo", True), ("pendiente_pago", False),
    ("creado", False), ("rechazado", False),
])
def test_study_is_enabled_when_paid_authorized_or_requiring_resample(factory, status, enabled):
    study_id = add_study(factory, status)
    with factory() as session:
        assert service(session).estudio_habilitado(study_id) is enabled


def test_missing_study_raises_lookup_error(factory):
    with factory() as session:
        with pytest.raises(LookupError):
            service(session).estudio_habilitado(999)
        with pytest.raises(LookupError):
            service(session).cambiar_estado_estudio(999, "pagado")


def test_invalid_status_raises_value_error_and_changes_nothing(factory):
    study_id = add_study(factory, "pendiente_pago")
    with factory() as session:
        with pytest.raises(ValueError):
            service(session).cambiar_estado_estudio(study_id, "inventado")
    with factory() as session:
        assert session.get(StudyModel, study_id).status == "pendiente_pago"


def test_status_change_is_persisted_when_the_caller_commits(factory):
    study_id = add_study(factory, "pendiente_pago")
    with factory() as session:
        service(session).cambiar_estado_estudio(study_id, "pagado")
        session.commit()
    with factory() as session:
        assert session.get(StudyModel, study_id).status == "pagado"
        assert service(session).estudio_habilitado(study_id) is True


def test_status_change_is_not_committed_by_the_service(factory):
    study_id = add_study(factory, "pendiente_pago")
    with factory() as session:
        service(session).cambiar_estado_estudio(study_id, "pagado")
        assert service(session).estudio_habilitado(study_id) is True  # visible en la misma sesión
        session.rollback()
    with factory() as session:
        assert session.get(StudyModel, study_id).status == "pendiente_pago"


def test_seed_without_demo_patient_creates_nothing(factory, capsys):
    assert seed_demo_studies(factory) == 0
    assert "no existe el paciente" in capsys.readouterr().out
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(StudyModel)) == 0


def test_seed_creates_three_studies_once(factory):
    patient_id = add_patient(factory)
    assert seed_demo_studies(factory) == 3
    assert seed_demo_studies(factory) == 0
    with factory() as session:
        statuses = session.scalars(select(StudyModel.status).where(StudyModel.patient_id == patient_id)).all()
        assert sorted(statuses) == ["autorizado", "pagado", "pendiente_pago"]
