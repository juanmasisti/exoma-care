from app.domain.entities.user import AuthenticatedUser
from app.domain.interfaces.user_repository import UserRepository
from app.infrastructure.database.security import verify_password


class InvalidCredentialsError(Exception):
    pass


class AutenticarUsuarioUseCase:
    def __init__(self, user_repository: UserRepository) -> None:
        self._user_repository = user_repository

    def execute(self, email: str, password: str) -> AuthenticatedUser:
        account = self._user_repository.get_by_email(email)
        if account is None or not verify_password(password, account.password_hash):
            raise InvalidCredentialsError("Email o contraseña inválidos.")

        return AuthenticatedUser(id=account.id, email=account.email, role=account.role)
