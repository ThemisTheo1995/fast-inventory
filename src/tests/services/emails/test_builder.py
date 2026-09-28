from unittest.mock import MagicMock

import pytest

from src.erp.services.emails.builder import (
    build_invite_email,
    build_onboard_email,
    build_welcome_email,
)
from src.erp.services.emails.schemas import EmailMessage


@pytest.fixture
def mock_renderer(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mocks renderer.render to avoid reading actual template files during unit tests."""
    mock = MagicMock()
    mock.render.return_value = ("rendered plain text", "<h1>rendered html</h1>")
    monkeypatch.setattr("src.erp.services.emails.builder.renderer", mock)
    return mock


# ==============================================================================
# build_welcome_email Tests
# ==============================================================================


def test_build_welcome_email_with_custom_base_url_and_user_name(mock_renderer: MagicMock):
    """Verifies welcome email construction with explicitly provided base_url and user_name."""
    # Arrange
    recipient = "alice@example.com"
    token = "xyz123token"
    user_name = "Alice"
    base_url = "https://staging.aegis.com/"  # Trailing slash to test rstrip('/')

    # Act
    msg = build_welcome_email(
        recipient=recipient,
        whitelisted_token=token,
        user_name=user_name,
        base_url=base_url,
    )

    # Assert
    expected_action_url = "https://staging.aegis.com/auth/verify?token=xyz123token"
    mock_renderer.render.assert_called_once_with(
        "welcome",
        {
            "user_name": "Alice",
            "action_url": expected_action_url,
        },
    )

    assert isinstance(msg, EmailMessage)
    assert msg.subject == "Welcome to Aegis — Your enterprise workspace is live"
    assert msg.recipients == ["alice@example.com"]
    assert msg.body_text == "rendered plain text"
    assert msg.body_html == "<h1>rendered html</h1>"


def test_build_welcome_email_defaults_from_settings(
    mock_renderer: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
):
    """Verifies default user_name and base_url resolution from get_settings()."""
    # Arrange
    fake_settings = type("Settings", (), {"DOMAIN_URL": "https://app.aegis.com"})()
    monkeypatch.setattr(
        "src.erp.services.emails.builder.get_settings",
        lambda: fake_settings,
    )

    # Act
    msg = build_welcome_email(recipient="bob@example.com", whitelisted_token="token456")

    # Assert
    expected_action_url = "https://app.aegis.com/auth/verify?token=token456"
    mock_renderer.render.assert_called_once_with(
        "welcome",
        {
            "user_name": "there",  # Default fallback name
            "action_url": expected_action_url,
        },
    )
    assert msg.recipients == ["bob@example.com"]


def test_build_welcome_email_fallback_settings_when_domain_url_missing(
    mock_renderer: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
):
    """Verifies fallback localhost URL when get_settings() has no DOMAIN_URL attribute."""
    # Arrange
    fake_settings = type("Settings", (), {})()
    monkeypatch.setattr(
        "src.erp.services.emails.builder.get_settings",
        lambda: fake_settings,
    )

    # Act
    build_welcome_email(recipient="charlie@example.com", whitelisted_token="token789")

    # Assert
    expected_action_url = "http://localhost:5173/auth/verify?token=token789"
    mock_renderer.render.assert_called_once_with(
        "welcome",
        {
            "user_name": "there",
            "action_url": expected_action_url,
        },
    )


# ==============================================================================
# build_onboard_email Tests
# ==============================================================================


def test_build_onboard_email_success(mock_renderer: MagicMock):
    """Verifies onboard email construction and context passing."""
    # Arrange
    recipient = "manager@acme.com"
    workspace_name = "Acme Corp"

    # Act
    msg = build_onboard_email(recipient=recipient, workspace_name=workspace_name)

    # Assert
    mock_renderer.render.assert_called_once_with(
        "onboard",
        {"workspace_name": "Acme Corp"},
    )

    assert isinstance(msg, EmailMessage)
    assert msg.subject == "Onboarding details for Aegis"
    assert msg.recipients == ["manager@acme.com"]
    assert msg.body_text == "rendered plain text"
    assert msg.body_html == "<h1>rendered html</h1>"


# ==============================================================================
# build_invite_email Tests
# ==============================================================================


def test_build_invite_email_success(mock_renderer: MagicMock):
    """Verifies invite email construction, formatted subject, and context passing."""
    # Arrange
    recipient = "newbie@acme.com"
    workspace_name = "Acme Corp"
    inviter_name = "Sarah"
    action_url = "https://app.aegis.com/auth/invite?token=invite123"

    # Act
    msg = build_invite_email(
        recipient=recipient,
        workspace_name=workspace_name,
        inviter_name=inviter_name,
        action_url=action_url,
    )

    # Assert
    mock_renderer.render.assert_called_once_with(
        "onboard",
        {
            "workspace_name": "Acme Corp",
            "inviter_name": "Sarah",
            "action_url": action_url,
        },
    )

    assert isinstance(msg, EmailMessage)
    assert msg.subject == "You've been invited to join Acme Corp"
    assert msg.recipients == ["newbie@acme.com"]
    assert msg.body_text == "rendered plain text"
    assert msg.body_html == "<h1>rendered html</h1>"
