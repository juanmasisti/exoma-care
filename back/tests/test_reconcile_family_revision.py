import json
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.infrastructure.database.reconcile_legacy_family_revision import reconcile_legacy_family_revision


@pytest.fixture
def legacy_database(tmp_path, monkeypatch):
    path=tmp_path/"legacy-family.db"
    monkeypatch.setenv("DATABASE_URL",f"sqlite:///{path}")
    config=Config(str(Path(__file__).resolve().parents[1]/"alembic.ini"))
    command.upgrade(config,"0003")
    engine=create_engine(f"sqlite:///{path}")
    # Reconstruir exactamente la antigua 0004 de familia sin aplicar logística.
    old_family=ScriptDirectory.from_config(config).get_revision("0005").module
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            old_family.upgrade()
        connection.execute(text("UPDATE alembic_version SET version_num='0004'"))
        connection.execute(text("""INSERT INTO users(id,username,role,first_name,last_name,phone,email,password_hash)
            VALUES(1,'demo','treating_physician','Demo','Prueba','000','demo@example.test','not-a-password')"""))
        connection.execute(text("""INSERT INTO patients(id,dni,nombre,apellido,version,clinical_summary)
            VALUES(1,'45000111','Paciente','Ficticio',2,'Clínica original')"""))
        connection.execute(text("""INSERT INTO patient_clinical_revisions(patient_id,version,changed_by_physician_id,changed_at,snapshot)
            VALUES(1,2,1,'2026-10-31 12:00:00',:data)"""),{"data":json.dumps({"evidence":"original"})})
        connection.execute(text("""INSERT INTO patient_family_records(patient_id,version,updated_at,updated_by_physician_id)
            VALUES(1,1,'2026-10-31 12:00:00',1)"""))
        connection.execute(text("""INSERT INTO family_members(id,patient_id,position,full_name,relationship,relationship_detail,diagnosis_status,notes)
            VALUES(7,1,0,'Familiar ficticio','mother','','unknown','Antecedente original')"""))
        connection.execute(text("""INSERT INTO patient_family_revisions(patient_id,version,changed_by_physician_id,changed_at,members)
            VALUES(1,1,1,'2026-10-31 12:00:00',:data)"""),{"data":json.dumps([{"full_name":"Familiar ficticio"}])})
    yield engine,config
    engine.dispose()


def original_rows(connection):
    return {name:connection.execute(text(f"SELECT * FROM {name}")).all() for name in
        ("users","patients","patient_clinical_revisions","patient_family_records","family_members","patient_family_revisions")}


def test_reconcile_populated_legacy_family_preserves_data_and_creates_logistics(legacy_database):
    engine,config=legacy_database
    with engine.connect() as connection:
        before=original_rows(connection)
    with engine.begin() as connection:
        assert reconcile_legacy_family_revision(connection) is True
    with engine.connect() as connection:
        assert original_rows(connection)==before
        assert connection.scalar(text("SELECT version_num FROM alembic_version"))=="0005"
        assert {"provinces","extraction_centers","holidays"}.issubset(inspect(connection).get_table_names())
    # Debe quedar reconocida por el flujo normal y ser repetible sin cambios.
    command.upgrade(config,"head")
    with engine.begin() as connection:
        assert reconcile_legacy_family_revision(connection) is False
        assert original_rows(connection)==before


def test_refuse_partial_legacy_family_without_creating_logistics(legacy_database):
    engine,_=legacy_database
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE family_member_symptoms")
    with pytest.raises(ValueError,match="esquema"):
        with engine.begin() as connection:
            reconcile_legacy_family_revision(connection)
    with engine.connect() as connection:
        assert "provinces" not in inspect(connection).get_table_names()
        assert connection.scalar(text("SELECT version_num FROM alembic_version"))=="0004"
        assert connection.scalar(text("SELECT count(*) FROM family_members"))==1


def test_standard_logistics_0004_must_use_normal_alembic_upgrade(tmp_path,monkeypatch):
    path=tmp_path/"logistics.db";monkeypatch.setenv("DATABASE_URL",f"sqlite:///{path}")
    config=Config(str(Path(__file__).resolve().parents[1]/"alembic.ini"))
    command.upgrade(config,"0004")
    engine=create_engine(f"sqlite:///{path}")
    with pytest.raises(ValueError,match="esquema"):
        with engine.begin() as connection:
            reconcile_legacy_family_revision(connection)
    command.upgrade(config,"head")
    with engine.connect() as connection:
        assert "patient_family_records" in inspect(connection).get_table_names()
    engine.dispose()


def test_failed_reconciliation_rolls_back_new_schema_and_version(legacy_database,monkeypatch):
    from app.infrastructure.database import reconcile_legacy_family_revision as repair
    engine,_=legacy_database
    def broken_upgrade():
        from alembic import op
        op.execute("CREATE TABLE unintended_table (id INTEGER)")
    monkeypatch.setattr(repair,"logistics_upgrade",broken_upgrade)
    with pytest.raises(ValueError,match="esquema"):
        with engine.begin() as connection:
            reconcile_legacy_family_revision(connection)
    with engine.connect() as connection:
        assert "unintended_table" not in inspect(connection).get_table_names()
        assert connection.scalar(text("SELECT version_num FROM alembic_version"))=="0004"
        assert connection.scalar(text("SELECT count(*) FROM family_members"))==1


def test_cli_default_is_read_only_and_apply_requires_backup(legacy_database,monkeypatch,capsys):
    from app.infrastructure.database.reconcile_legacy_family_revision import main
    engine,_=legacy_database
    monkeypatch.setattr("sys.argv",["reconcile"])
    main()
    assert "Inspección sin cambios" in capsys.readouterr().out
    monkeypatch.setattr("sys.argv",["reconcile","--apply"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code==2
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version"))=="0004"
        assert "provinces" not in inspect(connection).get_table_names()


def test_cli_creates_backup_and_preserves_existing_backup(legacy_database,tmp_path,monkeypatch):
    import sqlite3
    from app.infrastructure.database.reconcile_legacy_family_revision import main
    engine,_=legacy_database
    backup=tmp_path/"backup.db"
    backup.write_bytes(b"do-not-overwrite")
    monkeypatch.setattr("sys.argv",["reconcile","--apply","--backup",str(backup)])
    with pytest.raises(SystemExit):
        main()
    assert backup.read_bytes()==b"do-not-overwrite"
    backup2=tmp_path/"new-backup.db"
    monkeypatch.setattr("sys.argv",["reconcile","--apply","--backup",str(backup2)])
    main()
    with sqlite3.connect(backup2) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]=="0004"
        assert connection.execute("SELECT count(*) FROM family_members").fetchone()[0]==1
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version"))=="0005"
        assert connection.scalar(text("SELECT count(*) FROM family_members"))==1


def test_refuse_legacy_schema_with_changed_version_default(legacy_database):
    engine,_=legacy_database
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            from alembic import op
            with op.batch_alter_table("patient_family_records") as batch:
                batch.alter_column("version",server_default="2")
    with pytest.raises(ValueError,match="esquema"):
        with engine.begin() as connection:
            reconcile_legacy_family_revision(connection)
    with engine.connect() as connection:
        assert "provinces" not in inspect(connection).get_table_names()
        assert connection.scalar(text("SELECT version_num FROM alembic_version"))=="0004"
        assert connection.scalar(text("SELECT count(*) FROM family_members"))==1
