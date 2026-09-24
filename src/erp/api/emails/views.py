from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

import src.erp.services.emails as emails_module
from src.erp.core.config import get_settings

settings = get_settings()
router = APIRouter()

TEMPLATES_DIR = Path(emails_module.__file__).parent / "templates"
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Mock context definitions for previewing templates in dev
MOCK_PREVIEWS = {
    "welcome": {
        "user_name": "Themis",
        "action_url": "http://localhost:5173/auth/verify?token=preview-token-123",
        "whitelisted_token": "preview-token-123",
    },
    "onboard": {
        "user_name": "Alex",
        "workspace_name": "Aegis Corp",
    },
}


@router.get("/dev/preview-email/{email_name}", response_class=HTMLResponse)
async def preview_email(request: Request, email_name: str) -> HTMLResponse:
    """Dev-only endpoint to preview rendered Jinja email templates in browser."""
    if settings.ENVIRONMENT != "development":
        raise HTTPException(status_code=404, detail="Page not found")

    # 1. Fix: Construct template relative path WITHOUT leading slash
    template_filename = f"{email_name}.html.j2"
    full_path = (TEMPLATES_DIR / template_filename).resolve()

    # 2. Prevent directory traversal attacks and verify file exists
    if not full_path.is_relative_to(TEMPLATES_DIR.resolve()) or not full_path.exists():
        raise HTTPException(status_code=404, detail=f"Email template '{email_name}' not found at {full_path}")

    # 3. Build full rendering context with sensible defaults
    base_url = getattr(settings, "DOMAIN_URL", "http://localhost:5173").rstrip("/")

    context = {
        "base_url": base_url,
        "support_email": getattr(settings, "SUPPORT_EMAIL", "support@aegis-erp.com"),
        "current_year": datetime.now(UTC).year,
        **MOCK_PREVIEWS.get(email_name, {}),
    }

    # 4. Render template
    return templates.TemplateResponse(
        request=request,
        name=template_filename,
        context=context,
    )
