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
    snomed_url: str = ''
    snomed_api_key: SecretStr = SecretStr('')
    snomed_region: str = 'us-east-1'
    familiogram_base_url: str = ''
    familiogram_api_key: SecretStr = SecretStr('')
    apigen_group_id: str = 'grupo6'
    # Cupones (otro grupo). Un único gerente por grupo: el primer POST fija su id, así que
    # CUPONES_GERENTE_ID debe ser una constante estable antes de la primera llamada real.
    cupones_base_url: str = "https://vekuhonbpqtzakqbcoph.supabase.co/functions/v1/cupones-api"
    cupones_api_key: SecretStr | None = None
    cupones_gerente_id: str = "G-GRUPO6"
    # Obras sociales (Grupo 9).
    obras_sociales_base_url: str = "https://bxsvmfesrtjrqubblgws.supabase.co/functions/v1/api"
    obras_sociales_api_key: SecretStr | None = None
    chatbot_url: str = ''
    chatbot_apikey: SecretStr = SecretStr('')
    chatbot_token: SecretStr = SecretStr('')

    @field_validator('chatbot_url')
    @classmethod
    def validate_chatbot_url(cls, value):
        from urllib.parse import urlsplit
        value = value.strip()
        if value:
            parsed = urlsplit(value)
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError('CHATBOT_URL debe ser una URL HTTPS sin credenciales, query ni fragmento.')
        return value
    recorridos_api_url: str = "https://optimizacionapi.vercel.app/api/optimizacion"
    # Laboratorio Central (Calle 62 N° 555, La Plata): partida y destino del recorrido.
    central_lab_latitude: float = -34.921559
    central_lab_longitude: float = -57.938362
    # Lugar donde FedEx retira los lotes.
    central_lab_address: str = "Laboratorio Central, Calle 62 N° 555, La Plata"
    # API de FedEx (módulo 10, otro grupo). Credenciales del grupo solo en .env.
    fedex_url: str | None = None
    fedex_user: str | None = None
    fedex_pass: SecretStr | None = None
    # Secreto compartido con el bot de extracción (header X-Webhook-Secret). Sin valor, el webhook rechaza todo.
    extraction_webhook_secret: SecretStr | None = None
    # Herramientas de demo (simulador del bot en la app). Apagadas: sus endpoints dan 404.
    demo_tools_enabled: bool = False

    @field_validator("extraction_webhook_secret", mode="before")
    @classmethod
    def empty_webhook_secret_is_none(cls, value):
        return None if value == "" else value

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


def get_cupones_api_key() -> str:
    key = get_settings().cupones_api_key
    if key is None:
        raise RuntimeError("Configura CUPONES_API_KEY en back/.env o en el entorno.")
    return key.get_secret_value()


def get_cupones_base_url() -> str:
    return get_settings().cupones_base_url.rstrip("/")


def get_cupones_gerente_id() -> str:
    return get_settings().cupones_gerente_id.strip()


def get_obras_sociales_api_key() -> str:
    key = get_settings().obras_sociales_api_key
    if key is None:
        raise RuntimeError("Configura OBRAS_SOCIALES_API_KEY en back/.env o en el entorno.")
    return key.get_secret_value()


def get_obras_sociales_base_url() -> str:
    return get_settings().obras_sociales_base_url.rstrip("/")
