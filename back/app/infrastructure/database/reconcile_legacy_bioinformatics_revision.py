"""Reconcile the local database created before develop's 0007/0008 migrations.

Inspection is read-only by default. Applying requires a new SQLite backup outside
the repository and verifies the schema before recording revision 0013.
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
from app.infrastructure.database import (  # noqa: F401
    catalog_models,
    family_models,
    logistics_models,
    models,
    patient_clinical_models,
    study_models,
)

LOGISTICS_TABLES = {"appointments", "extraction_notices", "samples", "sample_events"}
LEGACY_REVISION = "0011"
INTEGRATED_REVISION = "0013"


def _metadata_without(excluded: set[str]) -> MetaData:
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        if table.name not in excluded:
            table.to_metadata(metadata)
    return metadata


def _require_schema(connection: Connection, metadata: MetaData) -> None:
    differences = compare_metadata(
        MigrationContext.configure(
            connection, opts={"compare_server_default": True}
        ),
        metadata,
    )
    if differences:
        raise ValueError(
            "El esquema no coincide exactamente con el esperado. "
            "No se modifica la base; revisar antes de continuar."
        )


def _state(connection: Connection) -> str:
    if connection.dialect.name != "sqlite":
        raise ValueError("Esta herramienta solo admite la base SQLite local.")
    tables = set(inspect(connection).get_table_names())
    if "alembic_version" not in tables:
        raise ValueError("La base no tiene revisión Alembic; no se modifica.")

    revisions = connection.scalars(
        text("SELECT version_num FROM alembic_version")
    ).all()
    if revisions == [INTEGRATED_REVISION]:
        _require_schema(connection, Base.metadata)
        return "integrated"
    if revisions != [LEGACY_REVISION]:
        raise ValueError(
            "La base no está en la revisión local 0011 esperada ni en 0013."
        )
    if LOGISTICS_TABLES & tables:
        raise ValueError(
            "La base tiene tablas de logística parciales; no se modifica "
            "automáticamente."
        )

    _require_schema(connection, _metadata_without(LOGISTICS_TABLES))
    return "legacy"


def reconcile_legacy_bioinformatics_revision(connection: Connection) -> bool:
    if connection.dialect.name != "sqlite":
        raise ValueError("Esta herramienta solo admite SQLite.")
    if not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
    if _state(connection) == "integrated":
        return False

    config = Config(str(BACK_DIR / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)
    with Operations.context(MigrationContext.configure(connection)):
        scripts.get_revision("0007").module.upgrade()
        scripts.get_revision("0008").module.upgrade()

    _require_schema(connection, Base.metadata)
    if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
        raise ValueError(
            "La base tiene referencias inválidas; se revierte la reconciliación."
        )
    if connection.exec_driver_sql("PRAGMA integrity_check").scalar() != "ok":
        raise ValueError(
            "La integridad de la base no es válida; se revierte la reconciliación."
        )
    connection.execute(
        text(
            "UPDATE alembic_version SET version_num=:revision "
            "WHERE version_num=:legacy"
        ),
        {"revision": INTEGRATED_REVISION, "legacy": LEGACY_REVISION},
    )
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplicar después de crear un respaldo nuevo.",
    )
    parser.add_argument(
        "--backup",
        type=Path,
        help="Ruta para un respaldo nuevo fuera del repositorio.",
    )
    args = parser.parse_args()

    url = make_url(get_settings().database_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        parser.error("Se requiere una base SQLite local en un archivo.")
    database = Path(url.database).resolve()
    if not database.is_file():
        parser.error("La base configurada no existe; no se crea una base nueva.")

    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            state = _state(connection)
        if state == "integrated":
            print("La base ya está integrada en 0013. No se modificó.")
            return
        if not args.apply:
            print(
                "Detectada la base local 0011 previa al merge. "
                "Inspección sin cambios; para aplicar se requiere "
                "--apply --backup RUTA_NUEVA."
            )
            return
        if args.backup is None:
            parser.error("--apply requiere --backup con una ruta nueva.")
        backup = args.backup.resolve()
        if (
            backup.exists()
            or backup == database
            or BACK_DIR.parent.resolve() in backup.parents
        ):
            parser.error(
                "El respaldo debe ser nuevo, distinto de la base y estar "
                "fuera del repositorio."
            )

        backup.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(
            f"{database.as_uri()}?mode=ro", uri=True
        ) as source, sqlite3.connect(backup) as destination:
            source.backup(destination)
        print(f"Respaldo creado: {backup}")

        with engine.begin() as connection:
            changed = reconcile_legacy_bioinformatics_revision(connection)
        if changed:
            print("Reconciliación completada: migraciones 0007/0008 y revisión 0013.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
