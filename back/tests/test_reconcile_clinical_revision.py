from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.autogenerate import compare_metadata
from sqlalchemy import create_engine, text
from app.infrastructure.database.reconcile_clinical_revision import reference_metadata, reconcile, main
from app.infrastructure.database.session import Base


@pytest.mark.parametrize("revision", ["0014", "0015"])
def test_reconcile_preserves_clinical_data_and_reaches_head(tmp_path, monkeypatch, revision):
    database = tmp_path / "clinical.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database}")
    engine = create_engine(f"sqlite:///{database}")
    reference_metadata(revision).create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
        connection.execute(text("INSERT INTO alembic_version VALUES (:v)"), {"v": revision})
        connection.execute(text("INSERT INTO symptoms(id,code,label,code_system) VALUES (1,'123456','Original','SNOMED')"))
        connection.execute(text("INSERT INTO pathologies(id,name,normalized_name,cardinal_symptom_id,apigen_code,apigen_group,cdss_code) VALUES (1,'Original','original',1,'FABRY','','FABRY')"))
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with pytest.raises(RuntimeError, match="previa al merge"):
        command.upgrade(config, "head")
    backup = tmp_path / "backup.db"
    monkeypatch.setattr("sys.argv", ["reconcile", "--apply", "--backup", str(backup)])
    main()
    assert backup.is_file()
    backup_engine = create_engine(f"sqlite:///{backup}")
    with backup_engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == revision
    backup_engine.dispose()
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0019"
        assert connection.scalar(text("SELECT apigen_code FROM pathologies WHERE id=1")) == "FABRY"
        assert connection.scalar(text("SELECT label FROM symptoms WHERE id=1")) == "Original"
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    with engine.begin() as connection:
        assert reconcile(connection) is False
    engine.dispose()


def test_partial_legacy_schema_is_rejected_without_changes(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'partial.db'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version(version_num TEXT)"))
        connection.execute(text("INSERT INTO alembic_version VALUES ('0015')"))
    with pytest.raises(ValueError, match="no coincide"):
        with engine.begin() as connection:
            reconcile(connection)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0015"
    engine.dispose()
