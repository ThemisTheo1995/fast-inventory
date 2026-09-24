import email
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import BotoCoreError, ClientError
from src.erp.services.emails.exceptions import EmailConfigurationError, EmailSendError
from src.erp.services.emails.providers.ses import SESEmailProvider, is_transient_aws_error
from src.erp.services.emails.schemas import EmailAttachment, EmailMessage

if TYPE_CHECKING:
    from email.message import Message

# ============================================================================
# Helper & Initialization Tests
# ============================================================================


def test_init_missing_configuration_raises_error():
    """Verifies that missing any required credential parameter raises EmailConfigurationError."""
    with pytest.raises(EmailConfigurationError, match="AWS region, keys and default sender"):
        SESEmailProvider(
            aws_region="",
            default_sender="sender@example.com",
            aws_access_key_id="key",
            aws_secret_access_key="secret",
        )


@pytest.mark.parametrize(
    "error_code, expected_transient",
    [
        ("Throttling", True),
        ("ThrottlingException", True),
        ("RequestLimitExceeded", True),
        ("ServiceUnavailable", True),
        ("InternalFailure", True),
        ("InternalError", True),
        ("MessageRejected", False),
        ("InvalidParameterValue", False),
        ("AccessDenied", False),
    ],
)
def test_is_transient_aws_error_client_errors(error_code: str, expected_transient: bool):
    """Verifies that only specific AWS ClientError codes are classified as transient."""
    error_response = {"Error": {"Code": error_code, "Message": "Test Error"}}
    exception = ClientError(error_response, "SendRawEmail")

    assert is_transient_aws_error(exception) is expected_transient


def test_is_transient_aws_error_botocore_error():
    """Verifies that generic BotoCoreError instances are always treated as transient."""
    exception = BotoCoreError()
    assert is_transient_aws_error(exception) is True


def test_is_transient_aws_error_non_aws_exception():
    """Verifies that non-AWS exceptions return False."""
    assert is_transient_aws_error(ValueError("Random error")) is False


# ============================================================================
# MIME Raw Email Construction (_build_raw_email) Tests
# ============================================================================


def test_build_raw_email_headers_and_defaults(ses_provider: SESEmailProvider):
    """Verifies MIME headers, fallback to default sender, and plain-text body structure."""
    message = EmailMessage(
        subject="Test Header Mapping",
        recipients=["to1@example.com", "to2@example.com"],
        body_text="Plain text body",
    )

    raw_bytes = ses_provider._build_raw_email(message)
    parsed: Message = email.message_from_bytes(raw_bytes)

    assert parsed["Subject"] == "Test Header Mapping"
    assert parsed["From"] == ses_provider.default_sender
    assert parsed["To"] == "to1@example.com, to2@example.com"
    assert "Cc" not in parsed
    assert "Reply-To" not in parsed

    # Verify body payload
    body_part = parsed.get_payload(0)
    text_part = body_part.get_payload(0)
    assert text_part.get_content_type() == "text/plain"
    assert text_part.get_payload(decode=True).decode("utf-8") == "Plain text body"


def test_build_raw_email_custom_sender_cc_and_reply_to(ses_provider: SESEmailProvider):
    """Verifies explicit sender override, CC, and Reply-To header generation."""
    message = EmailMessage(
        subject="Custom Config",
        recipients=["to@example.com"],
        sender="custom-sender@example.com",
        cc=["cc1@example.com", "cc2@example.com"],
        reply_to="reply@example.com",
        body_text="Body content",
    )

    raw_bytes = ses_provider._build_raw_email(message)
    parsed: Message = email.message_from_bytes(raw_bytes)

    assert parsed["From"] == "custom-sender@example.com"
    assert parsed["Cc"] == "cc1@example.com, cc2@example.com"
    assert parsed["Reply-To"] == "reply@example.com"


def test_build_raw_email_html_and_text_bodies(ses_provider: SESEmailProvider):
    """Verifies multipart/alternative structure when both HTML and text bodies are provided."""
    message = EmailMessage(
        subject="HTML Email",
        recipients=["to@example.com"],
        body_text="Plain text version",
        body_html="<h1>HTML Version</h1>",
    )

    raw_bytes = ses_provider._build_raw_email(message)
    parsed: Message = email.message_from_bytes(raw_bytes)

    # First child is the multipart/alternative body container
    alternative_part = parsed.get_payload(0)
    assert alternative_part.get_content_type() == "multipart/alternative"

    text_subpart, html_subpart = alternative_part.get_payload()

    assert text_subpart.get_content_type() == "text/plain"
    assert text_subpart.get_payload(decode=True).decode("utf-8") == "Plain text version"

    assert html_subpart.get_content_type() == "text/html"
    assert html_subpart.get_payload(decode=True).decode("utf-8") == "<h1>HTML Version</h1>"


def test_build_raw_email_multiple_attachments(ses_provider: SESEmailProvider):
    """Verifies attachment headers, filenames, MIME types, and payload encoding."""
    att1 = EmailAttachment(filename="doc.pdf", content=b"%PDF-1.4 sample", mime_type="application/pdf")
    att2 = EmailAttachment(filename="data.csv", content=b"col1,col2\nval1,val2", mime_type="text/csv")

    message = EmailMessage(
        subject="Email with Attachments",
        recipients=["to@example.com"],
        body_text="See attached files.",
        attachments=[att1, att2],
    )

    raw_bytes = ses_provider._build_raw_email(message)
    parsed: Message = email.message_from_bytes(raw_bytes)

    # Payload 0 = Body part, Payload 1 & 2 = Attachments
    assert len(parsed.get_payload()) == 3

    attachment1_part = parsed.get_payload(1)
    assert attachment1_part.get_filename() == "doc.pdf"
    assert attachment1_part.get_payload(decode=True) == b"%PDF-1.4 sample"

    attachment2_part = parsed.get_payload(2)
    assert attachment2_part.get_filename() == "data.csv"
    assert attachment2_part.get_payload(decode=True) == b"col1,col2\nval1,val2"


# ============================================================================
# Send Email Integration & Tag/Destination Mapping Tests
# ============================================================================


@pytest.mark.asyncio
async def test_send_email_deduplicates_destinations_and_formats_tags(ses_provider: SESEmailProvider):
    """Verifies that recipients, CC, and BCC are merged/deduplicated and tags are converted to SES format."""
    message = EmailMessage(
        subject="Destinations & Tags Test",
        recipients=["user1@example.com", "user2@example.com"],
        cc=["user2@example.com", "cc@example.com"],
        bcc=["bcc@example.com", "user1@example.com"],
        body_text="Checking destinations",
        tags={"environment": "production", "tenant": "acme"},
    )

    mock_client = MagicMock()
    mock_client.send_raw_email.return_value = {"MessageId": "msg-12345"}
    ses_provider.client = mock_client

    message_id = await ses_provider.send_email(message)

    assert message_id == "msg-12345"

    # Verify send_raw_email call kwargs
    mock_client.send_raw_email.assert_called_once()
    kwargs = mock_client.send_raw_email.call_args.kwargs

    # Check destinations deduplication
    expected_destinations = {"user1@example.com", "user2@example.com", "cc@example.com", "bcc@example.com"}
    assert set(kwargs["Destinations"]) == expected_destinations
    assert len(kwargs["Destinations"]) == 4

    # Check tags formatting
    expected_tags = [
        {"Name": "environment", "Value": "production"},
        {"Name": "tenant", "Value": "acme"},
    ]
    assert sorted(kwargs["Tags"], key=lambda x: x["Name"]) == sorted(expected_tags, key=lambda x: x["Name"])


# ============================================================================
# Retry Behavior & Exception Handling Tests
# ============================================================================


@pytest.mark.asyncio
@patch("tenacity.nap.sleep", return_value=None)  # Avoid actual sleeping during retry delay
async def test_retry_on_transient_error_recovers_and_succeeds(_mock_sleep, ses_provider: SESEmailProvider):
    """Verifies that transient errors (Throttling) trigger retries and return success if a retry succeeds."""
    throttling_error = ClientError({"Error": {"Code": "Throttling", "Message": "Rate exceeded"}}, "SendRawEmail")
    success_response = {"MessageId": "retried-msg-999"}

    mock_client = MagicMock()
    mock_client.send_raw_email.side_effect = [throttling_error, success_response]
    ses_provider.client = mock_client

    message = EmailMessage(
        subject="Retry Test",
        recipients=["to@example.com"],
        body_text="Retry test body",
    )

    message_id = await ses_provider.send_email(message)

    assert message_id == "retried-msg-999"
    assert mock_client.send_raw_email.call_count == 2


@pytest.mark.asyncio
@patch("tenacity.nap.sleep", return_value=None)
async def test_retry_exhausted_raises_email_send_error(_mock_sleep, ses_provider: SESEmailProvider):
    """Verifies that exhausting all retry attempts on persistent transient errors raises EmailSendError."""
    service_error = ClientError({"Error": {"Code": "ServiceUnavailable", "Message": "Outage"}}, "SendRawEmail")

    mock_client = MagicMock()
    mock_client.send_raw_email.side_effect = [service_error, service_error, service_error]
    ses_provider.client = mock_client

    message = EmailMessage(
        subject="Exhaust Retries",
        recipients=["to@example.com"],
        body_text="Will exhaust retries",
    )

    with pytest.raises(EmailSendError) as exc_info:
        await ses_provider.send_email(message)

    assert mock_client.send_raw_email.call_count == 3
    assert "ServiceUnavailable" in str(exc_info.value)
    assert exc_info.value.original_error == service_error


@pytest.mark.asyncio
async def test_non_transient_error_fails_immediately_without_retry(ses_provider: SESEmailProvider):
    """Verifies that permanent errors (e.g. MessageRejected) fail immediately on attempt 1."""
    rejected_error = ClientError(
        {"Error": {"Code": "MessageRejected", "Message": "Email address is not verified."}},
        "SendRawEmail",
    )

    mock_client = MagicMock()
    mock_client.send_raw_email.side_effect = rejected_error
    ses_provider.client = mock_client

    message = EmailMessage(
        subject="Non Transient Error",
        recipients=["unverified@example.com"],
        body_text="Fail fast",
    )

    with pytest.raises(EmailSendError) as exc_info:
        await ses_provider.send_email(message)

    assert mock_client.send_raw_email.call_count == 1
    assert "MessageRejected" in str(exc_info.value)


# ============================================================================
# Bulk Email Sending Tests
# ============================================================================


@pytest.mark.asyncio
async def test_send_bulk_emails_success(ses_provider: SESEmailProvider, ses_client):
    """Verifies concurrent dispatch and message ID collection for bulk emails."""
    ses_client.verify_email_identity(EmailAddress="bulk1@example.com")
    ses_client.verify_email_identity(EmailAddress="bulk2@example.com")

    messages = [
        EmailMessage(subject="Bulk 1", recipients=["bulk1@example.com"], body_text="Msg 1"),
        EmailMessage(subject="Bulk 2", recipients=["bulk2@example.com"], body_text="Msg 2"),
    ]

    message_ids = await ses_provider.send_bulk(messages)

    assert len(message_ids) == 2
    assert all(isinstance(m_id, str) and len(m_id) > 0 for m_id in message_ids)


@pytest.mark.asyncio
async def test_send_bulk_empty_list(ses_provider: SESEmailProvider):
    """Verifies handling of empty message lists in send_bulk."""
    message_ids = await ses_provider.send_bulk([])
    assert message_ids == []
