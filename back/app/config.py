"""Configuración compartida por API, herramientas y migraciones."""
from pathlib import Path

from pydantic import SecretStr, field_validator
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
    recorridos_api_url: str = "https://optimizacionapi.vercel.app/api/optimizacion"
    # Laboratorio Central (Calle 62 N° 555, La Plata): partida y destino del recorrido.
    central_lab_latitude: float = -34.921559
    central_lab_longitude: float = -57.938362

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
