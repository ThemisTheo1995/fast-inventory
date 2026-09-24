# tests/services/emails/test_schemas.py

import pytest
from pydantic import ValidationError

from src.erp.services.emails.schemas import EmailAttachment, EmailMessage

# ============================================================================
# EmailAttachment Tests
# ============================================================================


def test_email_attachment_defaults():
    """Verifies default content_type is set when not provided."""
    attachment = EmailAttachment(
        filename="report.pdf",
        content=b"sample binary content",
    )

    assert attachment.filename == "report.pdf"
    assert attachment.content == b"sample binary content"
    assert attachment.content_type == "application/octet-stream"


def test_email_attachment_custom_content_type():
    """Verifies custom content_type is properly set."""
    attachment = EmailAttachment(
        filename="data.csv",
        content=b"id,name\n1,test",
        content_type="text/csv",
    )

    assert attachment.content_type == "text/csv"


def test_email_attachment_validation_error():
    """Verifies ValidationError when required fields are missing."""
    with pytest.raises(ValidationError):
        EmailAttachment(filename="missing_content.txt")  # type: ignore[call-arg]


# ============================================================================
# EmailMessage Tests
# ============================================================================


def test_email_message_minimal_valid():
    """Verifies instantiation with only required fields and checks default values."""
    message = EmailMessage(
        subject="Welcome!",
        recipients=["user@example.com"],
        body_text="Hello world",
    )

    assert message.subject == "Welcome!"
    assert message.recipients == ["user@example.com"]
    assert message.body_text == "Hello world"
    assert message.body_html is None
    assert message.sender is None
    assert message.cc == []
    assert message.bcc == []
    assert message.reply_to is None
    assert message.attachments == []
    assert message.tags == {}


def test_email_message_full_valid():
    """Verifies instantiation with all optional fields, attachments, and tags populated."""
    attachment = EmailAttachment(
        filename="invoice.pdf",
        content=b"%PDF-1.4",
        content_type="application/pdf",
    )

    message = EmailMessage(
        subject="Invoice #101",
        recipients=["client@example.com"],
        body_text="Your invoice is attached.",
        body_html="<p>Your invoice is attached.</p>",
        sender="billing@company.com",
        cc=["accounting@company.com"],
        bcc=["archive@company.com"],
        reply_to="support@company.com",
        attachments=[attachment],
        tags={"environment": "staging", "category": "billing"},
    )

    assert len(message.recipients) == 1
    assert message.sender == "billing@company.com"
    assert message.cc == ["accounting@company.com"]
    assert message.bcc == ["archive@company.com"]
    assert message.reply_to == "support@company.com"
    assert len(message.attachments) == 1
    assert message.attachments[0].filename == "invoice.pdf"
    assert message.tags == {"environment": "staging", "category": "billing"}


def test_email_message_empty_recipients_raises_validation_error():
    """Verifies min_length constraint on recipients raises a ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        EmailMessage(
            subject="Test",
            recipients=[],  # min_length=1 constraint
            body_text="Test body",
        )

    assert "recipients" in str(exc_info.value)


def test_email_message_invalid_recipient_email_raises_validation_error():
    """Verifies invalid email format in recipients list fails validation."""
    with pytest.raises(ValidationError) as exc_info:
        EmailMessage(
            subject="Test",
            recipients=["not-an-email"],
            body_text="Test body",
        )

    assert "value is not a valid email address" in str(exc_info.value)


def test_email_message_invalid_cc_email_raises_validation_error():
    """Verifies invalid email format in CC list fails validation."""
    with pytest.raises(ValidationError) as exc_info:
        EmailMessage(
            subject="Test",
            recipients=["valid@example.com"],
            body_text="Test body",
            cc=["invalid-cc-email"],
        )

    assert "value is not a valid email address" in str(exc_info.value)
