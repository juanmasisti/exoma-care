from typing import Protocol

from app.domain.entities.user import UserAccount


class UserRepository(Protocol):
    def get_by_email(self, email: str) -> UserAccount | None:
        ...
