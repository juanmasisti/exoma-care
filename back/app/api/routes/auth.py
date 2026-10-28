from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, SecretStr

from app.api.dependencies import get_authenticate_user_use_case
from app.domain.entities.roles import UserRole
from app.infrastructure.security import create_access_token
from app.use_cases.authentication import (
    AutenticarUsuarioUseCase,
    InvalidCredentialsError,
)

router = APIRouter(prefix="/api/auth", tags=["autenticación"])


class LoginRequest(BaseModel):
    email: str
    password: SecretStr


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    rol: str
    redirect_to: str | None = None


@router.post(
    "/login",
    response_model=LoginResponse,
    response_model_exclude_none=True,
)
def login(
    credentials: LoginRequest,
    use_case: AutenticarUsuarioUseCase = Depends(get_authenticate_user_use_case),
) -> LoginResponse:
    try:
        user = use_case.execute(
            email=credentials.email,
            password=credentials.password.get_secret_value(),
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña inválidos.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    redirect_to = (
        "/paciente/dashboard" if user.role is UserRole.PATIENT else None
    )
    return LoginResponse(
        access_token=create_access_token(user),
        rol=user.role.display_name,
        redirect_to=redirect_to,
    )
