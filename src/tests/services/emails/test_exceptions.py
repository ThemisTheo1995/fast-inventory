# tests/services/emails/test_exceptions.py

from src.erp.services.emails.exceptions import (
    EmailConfigurationError,
    EmailSendError,
    EmailServiceError,
)


def test_email_service_error_base():
    """Verifies base EmailServiceError inheritance and string representation."""
    err = EmailServiceError("Base exception message")

    assert str(err) == "Base exception message"
    assert isinstance(err, Exception)


def test_email_configuration_error_inheritance():
    """Verifies EmailConfigurationError inherits from EmailServiceError."""
    err = EmailConfigurationError("Missing AWS region setting")

    assert str(err) == "Missing AWS region setting"
    assert isinstance(err, EmailServiceError)


def test_email_send_error_defaults_original_error_to_none():
    """Verifies EmailSendError initializes properly without an original error."""
    err = EmailSendError("Sending failed")

    assert str(err) == "Sending failed"
    assert err.original_error is None
    assert isinstance(err, EmailServiceError)


def test_email_send_error_stores_original_error():
    """Verifies EmailSendError correctly captures and preserves the underlying exception cause."""
    root_cause = ValueError("Connection timed out")
    err = EmailSendError("SES email sending failed", original_error=root_cause)

    assert str(err) == "SES email sending failed"
    assert err.original_error is root_cause
    assert isinstance(err.original_error, ValueError)
    assert str(err.original_error) == "Connection timed out"
    assert isinstance(err, EmailServiceError)
