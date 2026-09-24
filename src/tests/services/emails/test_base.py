import pytest

from src.erp.services.emails.base import BaseEmailProvider
from src.erp.services.emails.schemas import EmailMessage


class DummyEmailProvider(BaseEmailProvider):
    """Concrete subclass to invoke super() abstract methods for coverage."""

    async def send_email(self, message: EmailMessage) -> str:
        return await super().send_email(message)

    async def send_bulk(self, messages: list[EmailMessage]) -> list[str]:
        return await super().send_bulk(messages)


def test_base_email_provider_cannot_be_instantiated():
    """Verifies that BaseEmailProvider cannot be instantiated directly."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        BaseEmailProvider()


@pytest.mark.asyncio
async def test_base_email_provider_abstract_super_calls():
    """Executes super() calls to cover 'pass' statements in abstract methods."""
    provider = DummyEmailProvider()
    message = EmailMessage(
        subject="Test",
        recipients=["user@example.com"],
        body_text="Test body",
    )

    assert await provider.send_email(message) is None
    assert await provider.send_bulk([message]) is None
