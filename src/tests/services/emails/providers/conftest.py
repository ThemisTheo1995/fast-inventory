# tests/services/emails/test_ses_provider.py

import pytest
from src.erp.services.emails.providers.ses import SESEmailProvider


@pytest.fixture
def ses_provider(ses_client) -> SESEmailProvider:  # noqa
    """Instantiates SESEmailProvider pointing to the moto mock client."""
    return SESEmailProvider(
        aws_region="eu-west-1",
        default_sender="sender@example.com",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )
