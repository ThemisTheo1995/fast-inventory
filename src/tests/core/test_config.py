import pytest
from pydantic import ValidationError

from src.erp.core.config import Settings, get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Automatically clear the lru_cache before and after every single test.

    Without this, once get_settings() runs once, subsequent tests will receive
    the cached object and ignore any newly mocked environment variables.
    """
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def _mock_env_vars(monkeypatch):
    """A helper fixture providing a baseline set of valid environment variables.

    This prevents Pydantic from reading real local `.env` file during tests.
    """
    monkeypatch.setitem(Settings.model_config, "env_file", None)

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://user:pass@localhost:5432/test_db")
    monkeypatch.setenv("SHOPIFY_TEST_API_DOMAIN", "test.myshopify.com")
    monkeypatch.setenv("SHOPIFY_TEST_SECRET_API_KEY", "shppa_123456")
    monkeypatch.setenv("AUTH_SECRET_KEY", "super-secret-key-for-testing")
    monkeypatch.setenv("AUTH_ALGORITHM", "HS256")
    monkeypatch.setenv("AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    monkeypatch.setenv("AUTH_REFRESH_TOKEN_EXPIRE_DAYS", "7")


def test_settings_load_successfully(_mock_env_vars):
    """Verifies that with correct environment variables, settings load and type-cast correctly."""
    settings = get_settings()

    assert settings.ENVIRONMENT in ("dev", "test")
    assert settings.DATABASE_URL.startswith("postgresql://")
    assert settings.TEST_DATABASE_URL.startswith("postgresql://")
    assert settings.AUTH_ACCESS_TOKEN_EXPIRE_MINUTES == 30
    assert settings.AUTH_REFRESH_TOKEN_EXPIRE_DAYS == 7


def test_settings_override_environment(_mock_env_vars, monkeypatch):
    """Verifies that explicitly defining the ENVIRONMENT variable overrides the 'dev' default."""
    monkeypatch.setenv("ENVIRONMENT", "test")

    settings = get_settings()
    assert settings.ENVIRONMENT == "test"


@pytest.mark.parametrize("missing_var", ["DATABASE_URL", "SHOPIFY_TEST_API_DOMAIN", "AUTH_SECRET_KEY"])
def test_missing_required_variables_raises_validation_error(_mock_env_vars, monkeypatch, missing_var):
    """Verifies that if any required field is missing, Pydantic raises a ValidationError."""
    monkeypatch.delenv(missing_var, raising=False)

    with pytest.raises(ValidationError) as exc_info:
        get_settings()

    assert missing_var in str(exc_info.value)


def test_invalid_data_types_raises_validation_error(_mock_env_vars, monkeypatch):
    """Verifies that feeding bad data types (e.g., text instead of an int) throws errors."""
    monkeypatch.setenv("AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", "not-a-number")

    with pytest.raises(ValidationError) as exc_info:
        get_settings()

    assert "AUTH_ACCESS_TOKEN_EXPIRE_MINUTES" in str(exc_info.value)
