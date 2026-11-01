from pathlib import Path

import pytest

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.autogenerate import compare_metadata
from sqlalchemy import create_engine, inspect, text

from app.infrastructure.database.session import Base
from app.infrastructure.database import models, catalog_models, patient_clinical_models, logistics_models  # noqa: F401


def test_migrations_match_models_and_keep_existing_data(tmp_path, monkeypatch):
    database = tmp_path / "migrations.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database}")
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "0001")
    engine = create_engine(f"sqlite:///{database}")
    with engine.begin() as connection:
        connection.execute(text("""INSERT INTO users
            (id, username, role, first_name, last_name, phone, email, password_hash)
            VALUES (1, 'demo', 'medical_manager', 'Demo', 'Prueba', '000',
                    'demo@example.test', 'not-a-real-password')"""))
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM users")) == 1
        context = MigrationContext.configure(connection)
        assert compare_metadata(context, Base.metadata) == []
    command.downgrade(config, "0001")
    assert {"symptoms", "extraction_centers"}.isdisjoint(inspect(engine).get_table_names())
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM users")) == 1
    command.upgrade(config, "head")
    assert "extraction_centers" in inspect(engine).get_table_names()
    engine.dispose()


def test_clinical_migration_preserves_legacy_patient_and_blocks_unsafe_downgrade(tmp_path, monkeypatch):
    database = tmp_path / "legacy.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database}")
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "0002")
    engine = create_engine(f"sqlite:///{database}")
    with engine.begin() as connection:
        connection.execute(text("""INSERT INTO users
            (id, username, role, first_name, last_name, phone, email, password_hash)
            VALUES (1, 'legacy', 'patient', 'Ana', 'Prueba', '000',
                    'legacy@example.test', 'not-a-real-password')"""))
        connection.execute(text("""INSERT INTO patients
            (id, dni, nombre, apellido, usuario_id) VALUES (1, '45000111', 'Ana', 'Prueba', 1)"""))
    command.upgrade(config, "head")
    with engine.begin() as connection:
        legacy = connection.execute(text("SELECT dni, usuario_id, version, clinical_summary FROM patients WHERE id=1")).one()
        assert tuple(legacy) == ('45000111', 1, 1, None)
        connection.execute(text("""INSERT INTO patients
            (id, dni, nombre, apellido, usuario_id) VALUES (2, '45000222', 'Paciente', 'Pendiente', NULL)"""))
    with pytest.raises(RuntimeError, match="acceso pendiente"):
        command.downgrade(config, "0002")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM patients")) == 2
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0003"
        assert "patient_clinical_revisions" in inspect(connection).get_table_names()
    engine.dispose()
