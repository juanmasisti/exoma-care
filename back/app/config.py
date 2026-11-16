"""Configuración compartida por API, herramientas y migraciones."""
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACK_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACK_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
        frozen=True,
    )

    database_url: str = "sqlite:///./exoma_care.db"
    jwt_secret_key: SecretStr | None = None
    apigen_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APIGEN_BASE_URL", "API_GEN_URL"),
    )
    apigen_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("APIGEN_API_KEY", "API_SECRET_KEY_API_GEN"),
    )
    cdss_base_url: str = "https://genexoma.onrender.com/api/v1"
    cdss_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("CDSS_API_KEY", "API_SECRET_KEY_API_CDSS"),
    )
    notifications_base_url: str = (
        "https://jpnbycihugrzeeolobev.supabase.co/functions/v1"
    )
    notification_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "NOTIFICATIONS_API_KEY",
            "NOTIFICATION_API_KEY",
            "API_SECRET_KEY_API_NOTIFICATIONS",
        ),
    )

    @field_validator("jwt_secret_key", mode="before")
    @classmethod
    def validate_jwt_secret(cls, value):
        if value is None or value == "":
            return None
        secret = value.get_secret_value() if isinstance(value, SecretStr) else value
        if len(secret.encode("utf-8")) < 32:
            raise ValueError("JWT_SECRET_KEY debe tener al menos 32 bytes.")
        return value


def get_settings() -> Settings:
    # Las variables del proceso tienen prioridad sobre el archivo .env.
    return Settings()


def get_jwt_secret() -> str:
    secret = get_settings().jwt_secret_key
    if secret is None:
        raise RuntimeError("Configura JWT_SECRET_KEY en back/.env o en el entorno.")
    return secret.get_secret_value()


def get_apigen_api_key() -> str:
    key = get_settings().apigen_api_key
    if key is None:
        raise RuntimeError("Configura APIGEN_API_KEY en back/.env o en el entorno.")
    return key.get_secret_value()


def get_apigen_base_url() -> str:
    base_url = get_settings().apigen_base_url
    if not base_url:
        raise RuntimeError("Configura API_GEN_URL en back/.env o en el entorno.")
    return base_url.rstrip("/")


def get_cdss_api_key() -> str:
    key = get_settings().cdss_api_key
    if key is None:
        raise RuntimeError("Configura CDSS_API_KEY en back/.env o en el entorno.")
    return key.get_secret_value()


def get_cdss_base_url() -> str:
    return get_settings().cdss_base_url.rstrip("/")


def get_notification_api_key() -> str:
    key = get_settings().notification_api_key
    if key is None:
        raise RuntimeError("Configura NOTIFICATIONS_API_KEY en back/.env o en el entorno.")
    return key.get_secret_value()


def get_notifications_base_url() -> str:
    return get_settings().notifications_base_url.rstrip("/")
