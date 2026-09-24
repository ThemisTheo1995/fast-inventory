# tests/services/emails/test_factory.py

import pytest

from src.erp.core.config import get_settings
from src.erp.services.emails.exceptions import EmailConfigurationError
from src.erp.services.emails.factory import get_email_provider
from src.erp.services.emails.providers.console import ConsoleEmailProvider
from src.erp.services.emails.providers.ses import SESEmailProvider


@pytest.fixture(autouse=True)
def reset_factory_caches():
    """Clears both get_settings and get_email_provider LRU caches before/after each test."""
    get_settings.cache_clear()
    get_email_provider.cache_clear()
    yield
    get_settings.cache_clear()
    get_email_provider.cache_clear()


def test_get_email_provider_returns_console(monkeypatch):
    """Verifies factory returns a ConsoleEmailProvider when EMAIL_PROVIDER=console."""
    monkeypatch.setenv("EMAIL_PROVIDER", "console")

    provider = get_email_provider()

    assert isinstance(provider, ConsoleEmailProvider)


def test_get_email_provider_returns_ses(monkeypatch, ses_client):  # noqa
    """Verifies factory returns an SESEmailProvider when EMAIL_PROVIDER=ses."""
    monkeypatch.setenv("EMAIL_PROVIDER", "ses")
    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    monkeypatch.setenv("DEFAULT_FROM_EMAIL", "sender@example.com")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")

    provider = get_email_provider()

    assert isinstance(provider, SESEmailProvider)
    assert provider.default_sender == "sender@example.com"


def test_get_email_provider_handles_case_insensitivity(monkeypatch):
    """Verifies provider type parsing handles uppercase strings (e.g., 'CONSOLE')."""
    monkeypatch.setenv("EMAIL_PROVIDER", "CONSOLE")

    provider = get_email_provider()

    assert isinstance(provider, ConsoleEmailProvider)


def test_get_email_provider_raises_for_unsupported_provider(monkeypatch):
    """Verifies EmailConfigurationError is raised for invalid provider types."""
    monkeypatch.setenv("EMAIL_PROVIDER", "sendgrid")

    with pytest.raises(EmailConfigurationError) as exc_info:
        get_email_provider()

    assert "Unsupported email provider: 'sendgrid'" in str(exc_info.value)


def test_get_email_provider_caches_singleton_instance(monkeypatch):
    """Verifies @lru_cache returns the exact same object reference on subsequent calls."""
    monkeypatch.setenv("EMAIL_PROVIDER", "console")

    provider_a = get_email_provider()
    provider_b = get_email_provider()

    assert provider_a is provider_b
