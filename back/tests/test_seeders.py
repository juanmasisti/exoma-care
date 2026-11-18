from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.infrastructure.database.models import Paciente
from app.infrastructure.database.session import Base
from app.infrastructure.database.study_models import StudyGeneModel, StudyModel
from app.infrastructure.database.models import UserModel
from app.domain.entities.roles import UserRole
from seeders.patients import seed as seed_patient
from seeders.studies import DEMO_GENES, seed_bioinformatics_study


def test_bioinformatics_study_seeder_is_repeatable(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'seeders.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    with factory.begin() as session:
        patient = Paciente(dni="45000001", nombre="Demo", apellido="Paciente")
        session.add(patient)
        session.flush()
        patient_id = patient.id

    assert seed_bioinformatics_study(factory) == 1
    assert seed_bioinformatics_study(factory) == 0

    with factory() as session:
        studies = session.scalars(
            select(StudyModel).where(
                StudyModel.patient_id == patient_id,
                StudyModel.status == "en_area_bioinformatica",
            )
        ).all()
        assert len(studies) == 1
        genes = session.scalars(
            select(StudyGeneModel.symbol)
            .where(StudyGeneModel.study_id == studies[0].id)
            .order_by(StudyGeneModel.id)
        ).all()
        assert genes == list(DEMO_GENES)

    engine.dispose()


def test_bioinformatics_study_seeder_adds_genes_to_existing_demo_study(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'existing-seeder.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    with factory.begin() as session:
        patient = Paciente(dni="45000001", nombre="Demo", apellido="Paciente")
        session.add(patient)
        session.flush()
        session.add(StudyModel(patient_id=patient.id, status="en_analisis"))

    assert seed_bioinformatics_study(factory) == 0

    with factory() as session:
        study = session.scalar(select(StudyModel))
        genes = session.scalars(
            select(StudyGeneModel.symbol)
            .where(StudyGeneModel.study_id == study.id)
            .order_by(StudyGeneModel.id)
        ).all()
        assert genes == list(DEMO_GENES)

    engine.dispose()


def test_patient_seeder_creates_demo_patient_for_existing_account(
    tmp_path, monkeypatch
):
    from seeders import patients

    engine = create_engine(f"sqlite:///{tmp_path / 'patient-seeder.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(
            UserModel(
                username="patient-demo",
                role=UserRole.PATIENT,
                first_name="Paciente",
                last_name="Demo",
                phone="000",
                email="patient@example.test",
                national_id="45000001",
                password_hash="test-hash",
            )
        )
    monkeypatch.setattr(patients, "SessionLocal", factory)

    assert seed_patient() == 1
    assert seed_patient() == 0
    with factory() as session:
        patient = session.scalar(
            select(Paciente).where(Paciente.dni == "45000001")
        )
        assert patient is not None
        assert patient.usuario_id == 1
        assert patient.email == "patient@example.test"
    engine.dispose()
