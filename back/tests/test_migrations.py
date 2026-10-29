from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.autogenerate import compare_metadata
from sqlalchemy import create_engine, inspect, text

from app.infrastructure.database.session import Base
from app.infrastructure.database import models, catalog_models  # noqa: F401


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
    assert "symptoms" not in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM users")) == 1
    engine.dispose()
