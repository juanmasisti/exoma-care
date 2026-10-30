from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum as SQLAlchemyEnum, ForeignKey, String, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.entities.roles import UserRole
from app.infrastructure.database.session import Base


class Usuario(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    role: Mapped[UserRole] = mapped_column(
        SQLAlchemyEnum(
            UserRole,
            name="user_role",
            native_enum=True,
            values_callable=lambda roles: [role.value for role in roles],
        ),
        index=True,
    )
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(30))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    license_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    specialty: Mapped[str | None] = mapped_column(String(100), nullable=True)
    national_id: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    paciente: Mapped[Paciente | None] = relationship(back_populates="usuario", foreign_keys="Paciente.usuario_id")


class Paciente(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    dni: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(100))
    apellido: Mapped[str] = mapped_column(String(100))
    fecha_nacimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(30), nullable=True)
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=True,
    )
    usuario: Mapped[Usuario | None] = relationship(back_populates="paciente", foreign_keys=[usuario_id])
    created_by_physician_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", name="fk_patient_created_by"), index=True)
    email: Mapped[str | None] = mapped_column(String(255))
    clinical_summary: Mapped[str | None] = mapped_column(Text)
    suspicion_type: Mapped[str | None] = mapped_column(String(16))
    family_history: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __mapper_args__ = {"version_id_col": version}


# Keep the names used by the existing database seeder and application code.
UserModel = Usuario
