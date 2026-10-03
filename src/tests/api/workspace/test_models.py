import re

import pytest

from erp.api.workspace.models import Workspace

# ============================================================================
# Email Validation Tests
# ============================================================================


def test_workspace_email_valid_normalizes_to_lowercase():
    """Verifies valid emails pass validation and normalize to lowercase."""
    workspace = Workspace(name="Test HQ", email="Admin.User@Company.COM")
    assert workspace.email == "admin.user@company.com"


def test_workspace_email_empty_raises_value_error():
    """Verifies Empty email string raises ValueError."""
    with pytest.raises(ValueError, match=re.escape("Email address cannot be empty.")):
        Workspace(name="Test HQ", email="")


@pytest.mark.parametrize(
    "invalid_email",
    [
        "plainaddress",
        "#@%^%#$@#$@#.com",
        "@example.com",
        "Joe Smith <email@example.com>",
        "email.example.com",
        "email@example@example.com",
    ],
)
def test_workspace_email_invalid_format_raises_value_error(invalid_email: str):
    """Verifies malformed email strings raise ValueError with re.escape for safe matching."""
    expected_msg = f"Invalid email address format: {invalid_email}"
    with pytest.raises(ValueError, match=re.escape(expected_msg)):
        Workspace(name="Test HQ", email=invalid_email)


# ============================================================================
# Phone Number Validation Tests
# ============================================================================


def test_workspace_phone_number_valid_e164_success():
    """Verifies valid E.164 formatted phone numbers are accepted."""
    workspace = Workspace(name="Test HQ", email="test@company.com", phone_number="+14155552671")
    assert workspace.phone_number == "+14155552671"


def test_workspace_phone_number_empty_raises_value_error():
    """Verifies empty phone number string raises ValueError."""
    with pytest.raises(ValueError, match=re.escape("Phone number cannot be empty.")):
        Workspace(name="Test HQ", email="test@company.com", phone_number="")


@pytest.mark.parametrize(
    "invalid_phone",
    [
        "invalid-phone",
        "+0123456",
        "1234567890123456",
        "+1 (415) 555-2671",
        "abc-def-ghij",
    ],
)
def test_workspace_phone_number_invalid_format_raises_value_error(invalid_phone: str):
    """Verifies non-E.164 phone numbers raise ValueError with re.escape for safe matching."""
    expected_msg = f"Invalid phone number format: {invalid_phone}. Must be in E.164 format."
    with pytest.raises(ValueError, match=re.escape(expected_msg)):
        Workspace(name="Test HQ", email="test@company.com", phone_number=invalid_phone)
