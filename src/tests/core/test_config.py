import pytest
from pydantic import ValidationError

from src.erp.core.config import get_settings


@pytest.fixture
def _mock_env_vars(monkeypatch):
    """Provides a baseline set of valid environment variables in memory."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db")
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/test_db")
    monkeypatch.setenv("AUTH_SECRET_KEY", "super-secret-key-for-testing")
    monkeypatch.setenv("AUTH_ALGORITHM", "HS256")
    monkeypatch.setenv("AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", "5")
    monkeypatch.setenv("AUTH_REFRESH_TOKEN_EXPIRE_DAYS", "7")
    monkeypatch.setenv("COOKIE_SECURE", "0")
    monkeypatch.setenv("GEMINI_API_KEY", "Fake-key")
    monkeypatch.setenv("GEMINI_API_KEY_NAME", "Fake-Name")

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_settings_load_successfully(_mock_env_vars):
    """Verifies that with correct environment variables, settings load and type-cast correctly."""
    settings = get_settings()

    assert settings.ENVIRONMENT in ("development", "testing", "staging")
    assert settings.DATABASE_URL.startswith("postgresql+asyncpg://")
    assert settings.TEST_DATABASE_URL.startswith("postgresql+asyncpg://")
    assert settings.AUTH_ACCESS_TOKEN_EXPIRE_MINUTES == 5
    assert settings.AUTH_REFRESH_TOKEN_EXPIRE_DAYS == 7


def test_settings_override_environment(_mock_env_vars, monkeypatch):
    """Verifies that explicitly defining the ENVIRONMENT variable overrides the default."""
    monkeypatch.setenv("ENVIRONMENT", "test")

    settings = get_settings()
    assert settings.ENVIRONMENT == "test"


@pytest.mark.parametrize(
    "missing_var",
    [
        "DATABASE_URL",
    ],
)
def test_missing_required_variables_raises_validation_error(_mock_env_vars, monkeypatch, missing_var):
    """Verifies that if any required field is missing, Pydantic raises a ValidationError."""
    monkeypatch.delenv(missing_var, raising=False)

    get_settings.cache_clear()

    try:
        with pytest.raises(ValidationError) as exc_info:
            get_settings()

        assert missing_var in str(exc_info.value)
    finally:
        get_settings.cache_clear()


def test_invalid_data_types_raises_validation_error(_mock_env_vars, monkeypatch):
    """Verifies that feeding bad data types throws validation errors."""
    monkeypatch.setenv("AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", "not-a-number")

    with pytest.raises(ValidationError) as exc_info:
        get_settings()

    assert "AUTH_ACCESS_TOKEN_EXPIRE_MINUTES" in str(exc_info.value)
