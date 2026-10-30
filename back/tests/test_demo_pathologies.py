import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.session import Base
from app.infrastructure.database.catalog_models import PathologyModel, SymptomModel
from app.infrastructure.database.seed_demo_pathologies import seed_demo_pathologies


@pytest.fixture
def factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'demo.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(engine)
    engine.dispose()


def test_initial_five_pathologies_have_explicit_demo_concepts(factory):
    assert seed_demo_pathologies(factory) == 5
    with factory() as session:
        names = set(session.scalars(select(PathologyModel.name)))
        assert names == {"Enfermedad de Fabry", "Enfermedad de Pompe", "Mucopolisacaridosis tipo I", "Enfermedad de Gaucher", "ASMD"}
        assert session.scalar(select(func.count()).select_from(SymptomModel)) == 30
        assert set(session.scalars(select(SymptomModel.code_system))) == {"DEMO"}
        for pathology in session.scalars(select(PathologyModel)):
            assert pathology.cardinal_symptom not in pathology.secondary_symptoms
            assert len(pathology.secondary_symptoms) == 5


def test_repeated_seed_does_not_duplicate_or_overwrite_manager_edits(factory):
    seed_demo_pathologies(factory)
    with factory.begin() as session:
        fabry = session.scalar(select(PathologyModel).where(PathologyModel.name == "Enfermedad de Fabry"))
        fabry.secondary_symptoms = []
        fabry_id = fabry.id
    assert seed_demo_pathologies(factory) == 0
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(PathologyModel)) == 5
        assert session.scalar(select(func.count()).select_from(SymptomModel)) == 30
        assert session.get(PathologyModel, fabry_id).secondary_symptoms == []


def test_seed_preserves_preexisting_generic_demo_data(factory):
    with factory.begin() as session:
        session.add(SymptomModel(code="DEMO-1", label="Dato previo", code_system="DEMO"))
    seed_demo_pathologies(factory)
    with factory() as session:
        assert session.scalar(select(SymptomModel).where(SymptomModel.code == "DEMO-1")).label == "Dato previo"
