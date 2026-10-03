import pytest
from pydantic import ValidationError

from erp.core.config import get_settings


@pytest.fixture
def _mock_env_vars(monkeypatch):
    """Provides a baseline set of valid environment variables in memory."""
    get_settings.cache_clear()

    monkeypatch.setenv("ENVIRONMENT", "testing")
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db")
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/test_db")
    monkeypatch.setenv("AUTH_SECRET_KEY", "super-secret-key-for-testing")
    monkeypatch.setenv("AUTH_ALGORITHM", "HS256")
    monkeypatch.setenv("AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", "5")
    monkeypatch.setenv("AUTH_REFRESH_TOKEN_EXPIRE_DAYS", "7")
    monkeypatch.setenv("COOKIE_SECURE", "0")
    monkeypatch.setenv("GEMINI_API_KEY", "Fake-key")
    monkeypatch.setenv("GEMINI_API_KEY_NAME", "Fake-Name")
    monkeypatch.setenv("DEFAULT_FROM_EMAIL", "sender@example.com")
    monkeypatch.setenv("SUPPORT_EMAIL", "support@example.com")
    monkeypatch.setenv("BARCODE_GENERATION_SQS_QUEUE_URL", "test-sqs-queue-url")

    yield

    get_settings.cache_clear()


# ==============================================================================
# 1. SUCCESS & CACHE TESTS
# ==============================================================================


def test_settings_load_successfully(_mock_env_vars):
    """Verifies that settings load and type-cast correctly."""
    settings = get_settings()

    assert settings.ENVIRONMENT == "testing"
    assert settings.DATABASE_URL.startswith("postgresql+asyncpg://")
    assert settings.TEST_DATABASE_URL.startswith("postgresql+asyncpg://")
    assert settings.AUTH_ACCESS_TOKEN_EXPIRE_MINUTES == 5
    assert settings.AUTH_REFRESH_TOKEN_EXPIRE_DAYS == 7


def test_get_settings_lru_caching(_mock_env_vars):
    """Verifies get_settings caching behavior."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2

    get_settings.cache_clear()
    s3 = get_settings()
    assert s1 is not s3


# ==============================================================================
# 2. MISSING & INVALID VARIABLE TESTS
# ==============================================================================


def test_invalid_data_types_raises_validation_error(_mock_env_vars, monkeypatch):
    """Verifies that feeding non-integer data to integer fields raises ValidationError."""
    monkeypatch.setenv("AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", "not-a-number")
    get_settings.cache_clear()

    with pytest.raises(ValidationError) as exc_info:
        get_settings()

    assert "AUTH_ACCESS_TOKEN_EXPIRE_MINUTES" in str(exc_info.value)
