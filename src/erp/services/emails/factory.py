from functools import lru_cache

from erp.core.config import get_settings

from .base import BaseEmailProvider
from .exceptions import EmailConfigurationError
from .providers.console import ConsoleEmailProvider
from .providers.ses import SESEmailProvider


@lru_cache
def get_email_provider() -> BaseEmailProvider:
    """Factory dependency for FastAPI. Instantiates singleton instance based on application configuration."""
    settings = get_settings()

    provider_type = settings.EMAIL_PROVIDER.lower()

    if provider_type == "ses":
        return SESEmailProvider(
            aws_region=settings.AWS_REGION,
            default_sender=settings.DEFAULT_FROM_EMAIL,
        )

    if provider_type == "console":
        return ConsoleEmailProvider()

    msg = f"Unsupported email provider: '{provider_type}'"
    raise EmailConfigurationError(msg)
