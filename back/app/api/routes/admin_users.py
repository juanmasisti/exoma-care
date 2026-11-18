import re
import secrets
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.catalog_dependencies import require_roles
from app.api.dependencies import get_database_session
from app.domain.entities.roles import UserRole
from app.infrastructure.database.models import Usuario
from app.infrastructure.database.security import hash_password

router = APIRouter(
    prefix="/api/admin/users",
    tags=["administración de usuarios"],
    dependencies=[Depends(require_roles(UserRole.SUPER_ADMIN))],
)

ManagedRole = Literal[
    "treating_physician",
    "lab_administrator",
    "bioinformatician",
    "medical_manager",
]


class UserCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    role: ManagedRole
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=255)
    phone: str = Field(min_length=1, max_length=30)
    license_number: str | None = Field(default=None, max_length=50)
    specialty: str | None = Field(default=None, max_length=100)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.lower()
        if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized) is None:
            raise ValueError("Ingresá un email válido.")
        return normalized

    @model_validator(mode="after")
    def validate_physician_details(self) -> "UserCreateRequest":
        if self.role == "treating_physician":
            if not self.license_number or not self.specialty:
                raise ValueError(
                    "La matrícula y la especialidad son obligatorias para el médico tratante."
                )
        elif self.license_number is not None or self.specialty is not None:
            raise ValueError(
                "La matrícula y la especialidad solo corresponden al médico tratante."
            )
        return self


class UserSummary(BaseModel):
    id: int
    role: UserRole
    first_name: str
    last_name: str
    email: str
    phone: str
    license_number: str | None
    specialty: str | None


class UserCreatedResponse(UserSummary):
    temporary_password: str


@router.get("", response_model=list[UserSummary])
def list_managed_users(
    session: Session = Depends(get_database_session),
) -> list[Usuario]:
    roles = [
        UserRole.TREATING_PHYSICIAN,
        UserRole.LAB_ADMINISTRATOR,
        UserRole.BIOINFORMATICIAN,
        UserRole.MEDICAL_MANAGER,
    ]
    return list(
        session.scalars(
            select(Usuario)
            .where(Usuario.role.in_(roles))
            .order_by(Usuario.last_name, Usuario.first_name, Usuario.id)
        ).all()
    )


@router.post(
    "",
    response_model=UserCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_managed_user(
    body: UserCreateRequest,
    session: Session = Depends(get_database_session),
) -> UserCreatedResponse:
    duplicate = session.scalar(
        select(Usuario).where(
            or_(Usuario.email == body.email, Usuario.username == body.email)
        )
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese email.",
        )

    temporary_password = secrets.token_urlsafe(18)
    user = Usuario(
        username=body.email,
        role=UserRole(body.role),
        first_name=body.first_name,
        last_name=body.last_name,
        email=body.email,
        phone=body.phone,
        license_number=body.license_number,
        specialty=body.specialty,
        password_hash=hash_password(temporary_password),
    )
    session.add(user)
    try:
        session.commit()
        session.refresh(user)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese email.",
        ) from exc

    return UserCreatedResponse(
        id=user.id,
        role=user.role,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        phone=user.phone,
        license_number=user.license_number,
        specialty=user.specialty,
        temporary_password=temporary_password,
    )
