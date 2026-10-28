"""FastAPI dependency providers."""

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.infrastructure.database.session import SessionLocal
from app.infrastructure.repositories.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)
from app.use_cases.authentication import AutenticarUsuarioUseCase


def get_database_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def get_authenticate_user_use_case(
    session: Session = Depends(get_database_session),
) -> AutenticarUsuarioUseCase:
    repository = SQLAlchemyUserRepository(session)
    return AutenticarUsuarioUseCase(repository)
