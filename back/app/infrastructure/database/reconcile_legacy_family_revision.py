"""Reconciliación explícita de la antigua 0004 familiar local con la cadena integrada.

No se ejecuta al iniciar la API. Solo SQLite y esquema legado reconocido exactamente.
Por defecto inspecciona; --apply exige respaldo nuevo y verificación antes de registrar 0005.
"""
import argparse
from pathlib import Path
import sqlite3

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData, create_engine, inspect, text
from sqlalchemy.engine import Connection, make_url

from app.config import BACK_DIR, get_settings
from app.infrastructure.database.session import Base
from app.infrastructure.database import models, catalog_models, patient_clinical_models, family_models, logistics_models  # noqa: F401

LOGISTICS_TABLES = {"provinces", "extraction_centers", "holidays"}
FAMILY_TABLES = {"patient_family_records", "family_members", "family_member_symptoms", "family_member_diagnoses", "patient_family_revisions"}
# Migraciones posteriores a 0005: esta herramienta solo llega a 0005; lo que sigue es alembic upgrade.
REVISIONS_AFTER_0005 = {"0006"}
TABLES_AFTER_0005 = {"studies"}


def _require_schema(connection, metadata):
    if compare_metadata(MigrationContext.configure(connection, opts={"compare_server_default": True}), metadata):
        raise ValueError("El esquema no coincide exactamente con el esperado. No se modifica la base; revisar antes de continuar.")


def _metadata_without(excluded):
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        if table.name not in excluded:
            table.to_metadata(metadata)
    return metadata


def _legacy_state(connection: Connection) -> bool:
    if connection.dialect.name != "sqlite":
        raise ValueError("Esta herramienta solo admite la base SQLite local.")
    tables = set(inspect(connection).get_table_names())
    if "alembic_version" not in tables:
        raise ValueError("El esquema no tiene revisión Alembic; no se modifica.")
    revisions = connection.scalars(text("SELECT version_num FROM alembic_version")).all()
    if revisions == ["0005"]:
        _require_schema(connection, _metadata_without(TABLES_AFTER_0005))
        return False
    if len(revisions) == 1 and revisions[0] in REVISIONS_AFTER_0005:
        return False
    if revisions != ["0004"] or not FAMILY_TABLES.issubset(tables) or LOGISTICS_TABLES & tables:
        raise ValueError("El esquema no corresponde a la antigua 0004 familiar. Para una 0004 normal de logística usar alembic upgrade head.")
    _require_schema(connection, _metadata_without(LOGISTICS_TABLES | TABLES_AFTER_0005))
    return True


def logistics_upgrade():
    config = Config(str(BACK_DIR / "alembic.ini"))
    ScriptDirectory.from_config(config).get_revision("0004").module.upgrade()


def reconcile_legacy_family_revision(connection: Connection) -> bool:
    if connection.dialect.name != "sqlite":
        raise ValueError("Esta herramienta solo admite SQLite.")
    # Transacción SQLite real: también permite rollback de CREATE TABLE si la validación falla.
    if not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
    if not _legacy_state(connection):
        return False
    with Operations.context(MigrationContext.configure(connection)):
        logistics_upgrade()
    _require_schema(connection, _metadata_without(TABLES_AFTER_0005))
    if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
        raise ValueError("El esquema tiene referencias inválidas; se revierte la reconciliación.")
    if connection.exec_driver_sql("PRAGMA integrity_check").scalar() != "ok":
        raise ValueError("La integridad de la base no es válida; se revierte la reconciliación.")
    # Solo después de crear las tablas faltantes y comprobar todo el esquema.
    connection.execute(text("UPDATE alembic_version SET version_num='0005' WHERE version_num='0004'"))
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Aplicar después de crear respaldo y validar esquema.")
    parser.add_argument("--backup", type=Path, help="Ruta de un nuevo archivo de respaldo fuera del repositorio.")
    args = parser.parse_args()
    url = make_url(get_settings().database_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        parser.error("Se requiere un archivo SQLite local existente.")
    database = Path(url.database).resolve()
    if not database.is_file():
        parser.error("La base configurada no existe; no se crea una base nueva.")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            needed = _legacy_state(connection)
        if not needed:
            print("La base ya tiene el esquema integrado 0005 o posterior. No se modificó.")
            return
        if not args.apply:
            print("Detectada antigua 0004 familiar. Inspección sin cambios. Para reconciliar usar --apply --backup RUTA_NUEVA.")
            return
        if args.backup is None:
            parser.error("--apply requiere --backup con una ruta nueva fuera del repositorio.")
        backup = args.backup.resolve()
        if backup.exists() or backup == database or BACK_DIR.parent.resolve() in backup.parents:
            parser.error("El respaldo debe ser nuevo, distinto de la base y estar fuera del repositorio.")
        backup.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True) as source, sqlite3.connect(backup) as destination:
            source.backup(destination)
        print(f"Respaldo creado: {backup}")
        with engine.begin() as connection:
            changed = reconcile_legacy_family_revision(connection)
        print("Reconciliación completada: logística y familiares, revisión 0005." if changed else "La base ya estaba reconciliada.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
