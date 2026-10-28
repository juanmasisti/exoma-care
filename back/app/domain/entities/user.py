from dataclasses import dataclass

from app.domain.entities.roles import UserRole


@dataclass(frozen=True, slots=True)
class UserAccount:
    id: int
    email: str
    password_hash: str
    role: UserRole


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    id: int
    email: str
    role: UserRole
