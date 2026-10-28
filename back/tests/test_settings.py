import pytest
from pydantic import ValidationError

from app.config import Settings, get_jwt_secret


@pytest.fixture(autouse=True)
def clear_process_config(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)


def test_read_dotenv_and_hide_secret(tmp_path):
    key = "test-dotenv-secret-with-at-least-32-bytes"
    env_file = tmp_path / ".env"
    env_file.write_text(f"DATABASE_URL=sqlite:///demo.db\nJWT_SECRET_KEY={key}\nUNRELATED=value\n", encoding="utf-8")
    settings = Settings(_env_file=env_file)
    assert settings.database_url == "sqlite:///demo.db"
    assert settings.jwt_secret_key.get_secret_value() == key
    assert key not in repr(settings)


def test_process_environment_overrides_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=sqlite:///from-file.db\nJWT_SECRET_KEY=file-secret-with-at-least-32-bytes\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///from-process.db")
    monkeypatch.setenv("JWT_SECRET_KEY", "process-secret-with-at-least-32-bytes")
    settings = Settings(_env_file=env_file)
    assert settings.database_url == "sqlite:///from-process.db"
    assert settings.jwt_secret_key.get_secret_value() == "process-secret-with-at-least-32-bytes"


def test_missing_dotenv_does_not_prevent_migrations(tmp_path):
    settings = Settings(_env_file=tmp_path / "missing.env")
    assert settings.database_url == "sqlite:///./exoma_care.db"
    assert settings.jwt_secret_key is None


def test_empty_secret_does_not_sign_tokens(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "")
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        get_jwt_secret()


def test_short_secret_is_rejected_without_exposing_it():
    secret = "short-private-value"
    with pytest.raises(ValidationError) as failure:
        Settings(_env_file=None, jwt_secret_key=secret)
    assert secret not in str(failure.value)
