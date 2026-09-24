# src/erp/services/emails/renderer.py
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.erp.core.config import get_settings

TEMPLATES_DIR = Path(__file__).parent / "templates"


class EmailTemplateRenderer:
    def __init__(self, templates_dir: Path = TEMPLATES_DIR) -> None:
        self.env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=True,
        )

    def render(self, template_name: str, context: dict) -> tuple[str, str]:
        """
        Renders template_name.txt.j2 and template_name.html.j2 from the templates directory.
        """
        settings = get_settings()

        full_context = {
            "base_url": getattr(settings, "DOMAIN_URL", "http://localhost:5173").rstrip("/"),
            "support_email": getattr(settings, "SUPPORT_EMAIL", "support@aegis-erp.com"),
            "current_year": datetime.now(UTC).year,
            **context,
        }

        html_template = self.env.get_template(f"{template_name}.html.j2")
        text_template = self.env.get_template(f"{template_name}.txt.j2")

        return text_template.render(full_context), html_template.render(full_context)


renderer = EmailTemplateRenderer()
