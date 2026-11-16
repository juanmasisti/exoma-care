from uuid import UUID

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


class NotificacionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asunto: str = Field(min_length=1, max_length=200)
    mensaje: str = Field(min_length=1, max_length=10_000)
    destinatarios: list[str] = Field(min_length=1, max_length=50)
    idempotency_key: str = Field(min_length=1, max_length=200)
    referencia: str | None = None

    @field_validator("asunto", "mensaje")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("El texto no puede estar vacío.")
        return value

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("La Idempotency-Key no puede estar vacía.")
        return value

    @field_validator("destinatarios")
    @classmethod
    def validate_email_length(cls, value: list[str]) -> list[str]:
        normalized_emails = []
        for email in value:
            if len(email) > 320:
                raise ValueError("Cada correo debe tener como máximo 320 caracteres.")
            try:
                normalized_emails.append(
                    validate_email(
                        email, check_deliverability=False, test_environment=True
                    ).normalized
                )
            except EmailNotValidError as exc:
                raise ValueError(f"Correo electrónico inválido: {exc}") from exc
        return normalized_emails


class NotificacionResultado(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aviso_id: str
    estado: str = Field(min_length=1)
    creado: StrictBool

    @field_validator("aviso_id")
    @classmethod
    def validate_aviso_id(cls, value: str) -> str:
        try:
            UUID(value)
        except ValueError as exc:
            raise ValueError("El id del aviso debe ser un UUID válido.") from exc
        return value
