import pytest
from src.erp.services.emails.providers.console import ConsoleEmailProvider
from src.erp.services.emails.schemas import EmailAttachment, EmailMessage


@pytest.mark.asyncio
async def test_console_send_email_prints_and_returns_id(capsys: pytest.CaptureFixture[str]):
    """Verifies that send_email formats output to stdout and returns a console message ID."""
    provider = ConsoleEmailProvider()
    message = EmailMessage(
        subject="Dev Subject",
        recipients=["dev1@example.com", "dev2@example.com"],
        body_text="Hello dev team!",
    )

    message_id = await provider.send_email(message)

    # Verify return message ID format
    assert message_id.startswith("console-")

    # Capture and verify printed output
    captured = capsys.readouterr()
    assert "--- [MOCK EMAIL SENT] ---" in captured.out
    assert f"ID: {message_id}" in captured.out
    assert "To: dev1@example.com, dev2@example.com" in captured.out
    assert "Subject: Dev Subject" in captured.out
    assert "Body:\nHello dev team!" in captured.out
    assert "Attachments: 0" in captured.out


@pytest.mark.asyncio
async def test_console_send_email_with_attachments(capsys: pytest.CaptureFixture[str]):
    """Verifies attachment count is accurately included in the console output."""
    provider = ConsoleEmailProvider()
    attachment = EmailAttachment(
        filename="invoice.pdf",
        content=b"%PDF-1.4 sample content",
        mime_type="application/pdf",
    )
    message = EmailMessage(
        subject="Invoice #1001",
        recipients=["client@example.com"],
        body_text="Please find attached.",
        attachments=[attachment],
    )

    message_id = await provider.send_email(message)

    captured = capsys.readouterr()
    assert f"ID: {message_id}" in captured.out
    assert "Attachments: 1" in captured.out


@pytest.mark.asyncio
async def test_console_send_bulk_emails(capsys: pytest.CaptureFixture[str]):
    """Verifies bulk processing returns unique IDs and prints each message."""
    provider = ConsoleEmailProvider()
    messages = [
        EmailMessage(subject="Bulk 1", recipients=["user1@example.com"], body_text="Msg 1"),
        EmailMessage(subject="Bulk 2", recipients=["user2@example.com"], body_text="Msg 2"),
    ]

    message_ids = await provider.send_bulk(messages)

    assert len(message_ids) == 2
    assert all(m_id.startswith("console-") for m_id in message_ids)
    assert message_ids[0] != message_ids[1]

    captured = capsys.readouterr()
    assert f"ID: {message_ids[0]}" in captured.out
    assert f"ID: {message_ids[1]}" in captured.out


@pytest.mark.asyncio
async def test_console_send_bulk_empty_list():
    """Verifies bulk email sending handles an empty list gracefully."""
    provider = ConsoleEmailProvider()
    message_ids = await provider.send_bulk([])
    assert message_ids == []
