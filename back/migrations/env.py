import os

from alembic import context
from sqlalchemy import create_engine, pool

from app.infrastructure.database.session import Base
from app.infrastructure.database import models, catalog_models  # noqa: F401

url = os.environ.get("DATABASE_URL", "sqlite:///./exoma_care.db")

if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
