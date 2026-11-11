from pathlib import Path

import pytest

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.autogenerate import compare_metadata
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.infrastructure.database.session import Base
from app.infrastructure.database import models, catalog_models, patient_clinical_models, family_models, logistics_models, study_models  # noqa: F401


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
    assert {"extraction_centers", "patient_family_records", "studies", "appointments"}.issubset(inspect(engine).get_table_names())
    engine.dispose()


def test_appointment_indexes_from_the_migration_only_cover_booked(tmp_path, monkeypatch):
    # compare_metadata no compara el WHERE de los índices parciales: se prueba con datos.
    database = tmp_path / "appointments-migration.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database}")
    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")
    engine = create_engine(f"sqlite:///{database}")
    insert = text("""INSERT INTO appointments (study_id, center_id, starts_at, status, study_status_before, created_at)
        VALUES (:study, 1, :starts, :status, 'pagado', '2026-11-01 13:00:00')""")
    slot, other_slot = "2026-11-02 13:00:00", "2026-11-02 13:15:00"
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO provinces (id, name) VALUES (1, 'DEMO')"))
        connection.execute(text("""INSERT INTO extraction_centers (id, name, address, city, province_id, latitude, longitude, active)
            VALUES (1, 'Centro DEMO', 'Calle DEMO 1', 'DEMO', 1, 0, 0, 1)"""))
        connection.execute(text("INSERT INTO users (id, username, role, first_name, last_name, phone, email, password_hash) "
                                "VALUES (1, 'demo', 'patient', 'Demo', 'Prueba', '000', 'demo@example.test', 'x')"))
        connection.execute(text("INSERT INTO patients (id, dni, nombre, apellido, usuario_id) VALUES (1, '45000001', 'Demo', 'DEMO', 1)"))
        connection.execute(text("INSERT INTO studies (id, patient_id, status, created_at) "
                                "VALUES (1, 1, 'pagado', '2026-11-01'), (2, 1, 'pagado', '2026-11-01')"))
        connection.execute(insert, {"study": 1, "starts": slot, "status": "cancelled"})
        connection.execute(insert, {"study": 1, "starts": slot, "status": "booked"})  # mismo estudio y horario que el cancelado
    # Cada índice por separado, para que falte uno u otro la prueba falle.
    for study, starts, index in ((1, other_slot, "study_id"), (2, slot, "center_id, appointments.starts_at")):
        with engine.connect() as connection, pytest.raises(IntegrityError, match=f"appointments.{index}"):
            connection.execute(insert, {"study": study, "starts": starts, "status": "booked"})
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
    command.upgrade(config, "0003")
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


def test_family_migration_keeps_existing_clinical_evidence_and_pending_account(tmp_path, monkeypatch):
    import json
    database=tmp_path / "family-migration.db"
    monkeypatch.setenv("DATABASE_URL",f"sqlite:///{database}")
    config=Config(str(Path(__file__).resolve().parents[1]/"alembic.ini"))
    command.upgrade(config,"0003")
    engine=create_engine(f"sqlite:///{database}")
    with engine.begin() as connection:
        connection.execute(text("""INSERT INTO users
            (id,username,role,first_name,last_name,phone,email,password_hash)
            VALUES (1,'doctor','treating_physician','Demo','Prueba','000','demo@example.test','not-a-password')"""))
        connection.execute(text("""INSERT INTO patients
            (id,dni,nombre,apellido,usuario_id,clinical_summary,version)
            VALUES (1,'45000111','Ana','Prueba',NULL,'Texto clínico previo',2)"""))
        connection.execute(text("""INSERT INTO patient_clinical_revisions
            (patient_id,version,changed_by_physician_id,changed_at,snapshot)
            VALUES (1,2,1,'2026-10-31 12:00:00',:snapshot)"""),{"snapshot":json.dumps({"previous":"evidence"})})
    command.upgrade(config,"head")
    with engine.connect() as connection:
        assert tuple(connection.execute(text("SELECT usuario_id,clinical_summary,version FROM patients WHERE id=1")).one())==(None,'Texto clínico previo',2)
        assert json.loads(connection.scalar(text("SELECT snapshot FROM patient_clinical_revisions")))=={"previous":"evidence"}
        assert connection.scalar(text("SELECT count(*) FROM patient_family_records"))==0
        assert compare_metadata(MigrationContext.configure(connection),Base.metadata)==[]
    command.downgrade(config,"0003")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM patient_clinical_revisions"))==1
        assert connection.scalar(text("SELECT count(*) FROM patients"))==1
    engine.dispose()


def test_migration_history_has_one_unique_head_after_logistics_and_family_integration():
    from alembic.script import ScriptDirectory
    config=Config(str(Path(__file__).resolve().parents[1]/"alembic.ini"))
    scripts=ScriptDirectory.from_config(config)
    assert scripts.get_heads()==["0007"]
    assert scripts.get_revision("0004").path.endswith("0004_extraction_centers.py")
    assert scripts.get_revision("0005").down_revision=="0004"
    assert scripts.get_revision("0006").down_revision=="0005"
    assert scripts.get_revision("0007").down_revision=="0006"
