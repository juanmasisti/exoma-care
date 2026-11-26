from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities.roles import UserRole
from app.domain.entities.user import UserAccount
from app.domain.interfaces.user_repository import UserRepository
from app.infrastructure.database.models import Usuario


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_email(self, email: str) -> UserAccount | None:
        user = self._session.scalar(select(Usuario).where(Usuario.email == email))
        if user is None:
            return None

        return UserAccount(
            id=user.id,
            email=user.email,
            password_hash=user.password_hash,
            role=UserRole(user.role),
        )
