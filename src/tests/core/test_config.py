from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from erp.core.config import _fetch_bitwarden_secrets, get_settings


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


# ==============================================================================
# 2. BWS settings
# ==============================================================================


@pytest.fixture
def mock_bws_env(monkeypatch: pytest.MonkeyPatch):
    """Fixture to safely inject valid BWS environment variables."""
    monkeypatch.setenv("BWS_ACCESS_TOKEN", "mock_token")
    monkeypatch.setenv("BWS_PROJECT_ID", "mock_project_id")
    monkeypatch.setenv("BWS_ORG_ID", "mock_org_id")


def test_fetch_secrets_missing_env(monkeypatch: pytest.MonkeyPatch):
    """Test that an empty dict is returned if BWS vars are missing."""
    monkeypatch.delenv("BWS_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("BWS_PROJECT_ID", raising=False)
    monkeypatch.delenv("BWS_ORG_ID", raising=False)

    result = _fetch_bitwarden_secrets()
    assert result == {}


@patch("erp.core.config.BitwardenClient")
@patch("erp.core.config.client_settings_from_dict")
def test_fetch_secrets_success(mock_settings, mock_client_cls, mock_bws_env):  # noqa
    """Test successful fetching and parsing of secrets."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    # Mock secrets list response
    mock_secret_identifier = MagicMock()
    mock_secret_identifier.id = "secret-id-1"

    mock_list_response = MagicMock()
    mock_list_response.success = True
    mock_list_response.data = [mock_secret_identifier]
    mock_client.secrets.return_value.list.return_value = mock_list_response

    # Mock secrets get_by_ids response
    mock_secret_detail = MagicMock()
    mock_secret_detail.key = "DATABASE_URL"
    mock_secret_detail.value = "postgres://localhost/bws_db"

    mock_get_response = MagicMock()
    mock_get_response.success = True
    mock_get_response.data = [mock_secret_detail]
    mock_client.secrets.return_value.get_by_ids.return_value = mock_get_response

    # Execute
    result = _fetch_bitwarden_secrets()

    # Assertions
    assert result == {"DATABASE_URL": "postgres://localhost/bws_db"}
    mock_client.auth.return_value.login_access_token.assert_called_once_with("mock_token")
    mock_client.secrets.return_value.get_by_ids.assert_called_once_with(["secret-id-1"])


@patch("erp.core.config.logger")
@patch("erp.core.config.BitwardenClient")
@patch("erp.core.config.client_settings_from_dict")
def test_fetch_secrets_exception_handling(mock_settings, mock_client_cls, mock_logger, mock_bws_env):  # noqa
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.secrets.return_value.list.side_effect = Exception("API connection failed")

    result = _fetch_bitwarden_secrets()

    assert result == {}
    mock_logger.warning.assert_called_once()
    assert "Bitwarden fetch skipped/failed" in mock_logger.warning.call_args[0][0]
