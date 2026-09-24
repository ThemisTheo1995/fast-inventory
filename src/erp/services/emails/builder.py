# src/erp/services/emails/builders.py
from src.erp.core.config import get_settings
from src.erp.services.emails.renderer import renderer
from src.erp.services.emails.schemas import EmailMessage


def build_welcome_email(
    recipient: str,
    whitelisted_token: str,
    user_name: str = "there",
    base_url: str | None = None,
) -> EmailMessage:
    if base_url is None:
        base_url = getattr(get_settings(), "DOMAIN_URL", "http://localhost:5173")

    action_url = f"{base_url.rstrip('/')}/auth/verify?token={whitelisted_token}"

    context = {
        "user_name": user_name,
        "action_url": action_url,
    }

    body_text, body_html = renderer.render("welcome", context)

    return EmailMessage(
        subject="Welcome to Aegis — Your enterprise workspace is live",
        recipients=[recipient],
        body_text=body_text,
        body_html=body_html,
    )


def build_onboard_email(recipient: str, workspace_name: str) -> EmailMessage:
    context = {"workspace_name": workspace_name}
    body_text, body_html = renderer.render("onboard", context)

    return EmailMessage(
        subject="Onboarding details for Aegis",
        recipients=[recipient],
        body_text=body_text,
        body_html=body_html,
    )


def build_invite_email(recipient: str, workspace_name: str, inviter_name: str, action_url: str) -> EmailMessage:
    context = {"workspace_name": workspace_name, "inviter_name": inviter_name, "action_url": action_url}
    body_text, body_html = renderer.render("onboard", context)

    return EmailMessage(
        subject=f"You've been invited to join {workspace_name}",
        recipients=[recipient],
        body_text=body_text,
        body_html=body_html,
    )
