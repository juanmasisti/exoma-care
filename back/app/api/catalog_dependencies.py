import os

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.dependencies import get_database_session
from app.domain.entities.roles import UserRole
from app.domain.entities.user import AuthenticatedUser
from app.infrastructure.database.models import Usuario
from app.infrastructure.repositories.sqlalchemy_pathology_repository import SQLAlchemyPathologyRepository
from app.use_cases.pathologies import PathologyCatalog

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: Session = Depends(get_database_session),
) -> AuthenticatedUser:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="La sesión no es válida o venció.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    secret = os.environ.get("JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError("La variable JWT_SECRET_KEY es obligatoria.")
    try:
        payload = jwt.decode(credentials.credentials, secret, algorithms=["HS256"],
                             options={"require": ["sub", "exp", "iat"]})
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise unauthorized from None
    user = session.get(Usuario, user_id)
    if user is None:
        raise unauthorized
    # Se consulta el rol actual en BD: una modificación no conserva permisos viejos.
    return AuthenticatedUser(user.id, user.email, UserRole(user.role))


def require_roles(*roles: UserRole):
    def authorize(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Tu rol no permite esta operación.")
        return user
    return authorize


def get_catalog(session: Session = Depends(get_database_session)) -> PathologyCatalog:
    return PathologyCatalog(SQLAlchemyPathologyRepository(session))
