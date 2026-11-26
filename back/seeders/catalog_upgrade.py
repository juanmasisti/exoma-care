"""Explicit upgrade; inspection never creates a database or runs migrations."""
from pathlib import Path
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from app.config import get_settings
from seeders.clinical_catalog import prepare_catalog

def run(apply=False):
    url = get_settings().database_url
    if url.startswith("sqlite:///"):
        path = Path(url[len("sqlite:///"):])
        if not path.is_file():
            raise ValueError("La base no existe. Prepará primero una base nueva con seeders.")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            current = set(connection.execute(text("SELECT version_num FROM alembic_version")).scalars())
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        if current != set(ScriptDirectory.from_config(config).get_heads()):
            raise ValueError("Actualizá y respaldá la base según la guía antes de continuar.")
        for item in prepare_catalog(apply=apply, upgrade=True):
            print(item["name"], item["action"])
    finally:
        engine.dispose()
