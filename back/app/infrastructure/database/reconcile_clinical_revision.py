"""Inspect or reconcile the pre-merge clinical 0014/0015 SQLite schemas.

No application startup migration. --apply requires a new backup outside the repo.
"""
import argparse
import sqlite3
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData, create_engine, inspect, text
from sqlalchemy.engine import make_url
from app.config import BACK_DIR, get_settings


def scripts():
    return ScriptDirectory.from_config(Config(str(BACK_DIR / "alembic.ini")))


def legacy_revision(connection):
    tables = set(inspect(connection).get_table_names())
    if "alembic_version" not in tables:
        return None
    revisions = connection.scalars(text("SELECT version_num FROM alembic_version")).all()
    if len(revisions) != 1:
        raise ValueError("Se requiere una única revisión Alembic.")
    revision = revisions[0]
    if revision in ("0014", "0015") and "study_budgets" not in tables:
        return revision
    return None


def reference_metadata(legacy):
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                chain = scripts()
                for revision in reversed(list(chain.iterate_revisions("0013", "base"))):
                    revision.module.upgrade()
                # Clinical migrations used these two numeric IDs before the merge.
                chain.get_revision("0015").module.upgrade()
                if legacy == "0015":
                    chain.get_revision("0016").module.upgrade()
            metadata = MetaData()
            metadata.reflect(connection)
            return metadata
    finally:
        engine.dispose()


def require_legacy_schema(connection, revision):
    if connection.dialect.name != "sqlite":
        raise ValueError("La conversión solo admite SQLite.")
    differences = compare_metadata(MigrationContext.configure(connection,
        opts={"compare_server_default": True}), reference_metadata(revision))
    if differences:
        raise ValueError("El esquema no coincide con la rama clínica original; no se modifica.")


def reconcile(connection):
    if not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
    revision = legacy_revision(connection)
    if revision is None:
        return False
    require_legacy_schema(connection, revision)
    with Operations.context(MigrationContext.configure(connection)):
        scripts().get_revision("0014").module.upgrade()
    if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
        raise ValueError("Hay referencias inválidas; se revierte la conversión.")
    if connection.exec_driver_sql("PRAGMA integrity_check").scalar() != "ok":
        raise ValueError("Falló la comprobación de integridad.")
    connection.execute(text("UPDATE alembic_version SET version_num=:version"),
        {"version": "0016" if revision == "0015" else "0015"})
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    url = make_url(get_settings().database_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        parser.error("Se requiere un archivo SQLite existente.")
    database = Path(url.database).resolve()
    if not database.is_file():
        parser.error("No existe la base configurada.")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            revision = legacy_revision(connection)
            if revision is None:
                print("No requiere conversión. Continuar con alembic upgrade head.")
                return
            require_legacy_schema(connection, revision)
        if not args.apply:
            print("Base clínica anterior al merge detectada. Usar --apply --backup RUTA_NUEVA.")
            return
        if args.backup is None:
            parser.error("--apply requiere --backup fuera del repositorio.")
        backup = args.backup.resolve()
        if backup.exists() or backup == database or BACK_DIR.parent.resolve() in backup.parents:
            parser.error("El respaldo debe ser nuevo y estar fuera del repositorio.")
        backup.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation prevents overwriting any existing backup.
        with backup.open("xb"):
            pass
        with sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True) as source, sqlite3.connect(backup) as destination:
            source.backup(destination)
        with engine.begin() as connection:
            reconcile(connection)
        print(f"Conversión completada; respaldo: {backup}. Ejecutar alembic upgrade head.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
