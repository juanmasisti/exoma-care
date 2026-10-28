import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.domain.interfaces.pathology_repository import DuplicatePathologyName
from app.infrastructure.database.session import Base
from app.infrastructure.database.catalog_models import PathologyModel, SymptomModel
from app.infrastructure.repositories.sqlalchemy_pathology_repository import SQLAlchemyPathologyRepository
from app.use_cases.pathologies import PathologyCatalog


@pytest.fixture
def database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'catalog.db'}")
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([SymptomModel(id=i, code=f"DEMO-{i}", label=f"Síntoma demo {i}",
                                     code_system="DEMO") for i in range(1, 5)])
        session.commit()
    yield engine
    engine.dispose()


def test_create_then_read_in_another_session(database):
    with Session(database) as session:
        saved = PathologyCatalog(SQLAlchemyPathologyRepository(session)).save("  Prueba  A ", 1, [2, 3, 3])
    with Session(database) as session:
        catalog = PathologyCatalog(SQLAlchemyPathologyRepository(session))
        loaded = catalog.get(saved.id)
        assert loaded.name == "Prueba A"
        assert [s.id for s in loaded.secondary_symptoms] == [2, 3]
        assert catalog.validate(saved.id, [2, 3]).valid


def test_edit_replaces_associations(database):
    with Session(database) as session:
        catalog = PathologyCatalog(SQLAlchemyPathologyRepository(session))
        saved = catalog.save("Prueba", 1, [2, 3])
        changed = catalog.save("Editada", 2, [4], saved.id)
        assert changed.cardinal_symptom.id == 2
        assert [s.id for s in changed.secondary_symptoms] == [4]
        assert not catalog.validate(saved.id, [1, 3]).valid


@pytest.mark.parametrize("name,cardinal,secondary", [("", 1, [2]), ("Prueba", 1, [1]),
                                                     ("Prueba", 999, [2]), ("Prueba", 1, [999])])
def test_invalid_definition_does_not_persist(database, name, cardinal, secondary):
    with Session(database) as session:
        catalog = PathologyCatalog(SQLAlchemyPathologyRepository(session))
        with pytest.raises(ValueError):
            catalog.save(name, cardinal, secondary)
        assert session.scalars(select(PathologyModel)).all() == []


def test_duplicate_normalized_name(database):
    with Session(database) as session:
        catalog = PathologyCatalog(SQLAlchemyPathologyRepository(session))
        catalog.save("Prueba A", 1, [2])
        with pytest.raises(DuplicatePathologyName):
            catalog.save(" prueba   a ", 2, [3])


def test_unknown_ids_are_not_silently_ignored(database):
    with Session(database) as session:
        catalog = PathologyCatalog(SQLAlchemyPathologyRepository(session))
        saved = catalog.save("Prueba", 1, [2, 3])
        with pytest.raises(ValueError, match="terminología"):
            catalog.validate(saved.id, [1, 999])
        with pytest.raises(LookupError):
            catalog.save("Inexistente", 1, [], 999)
