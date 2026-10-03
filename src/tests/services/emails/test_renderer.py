from datetime import UTC, datetime
from pathlib import Path

import pytest
from jinja2.exceptions import TemplateNotFound

from src.erp.services.emails.renderer import EmailTemplateRenderer, renderer


@pytest.fixture
def temp_templates_dir(tmp_path: Path) -> Path:
    """Creates temporary email template files for testing."""
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()

    txt_content = (
        "Hello {{ user_name }},\n"
        "Welcome to {{ base_url }}!\n"
        "Contact us at {{ support_email }}.\n"
        "Copyright {{ current_year }}."
    )
    (templates_dir / "welcome.txt.j2").write_text(txt_content, encoding="utf-8")

    html_content = (
        "<h1>Hello {{ user_name }}</h1>\n"
        '<a href="{{ base_url }}">Home</a>\n'
        "<p>Support: {{ support_email }}</p>\n"
        "<footer>{{ current_year }}</footer>"
    )
    (templates_dir / "welcome.html.j2").write_text(html_content, encoding="utf-8")

    return templates_dir


@pytest.fixture
def mock_renderer(temp_templates_dir: Path) -> EmailTemplateRenderer:
    """Returns an EmailTemplateRenderer pointing to temporary templates."""
    return EmailTemplateRenderer(templates_dir=temp_templates_dir)


def test_render_success_and_context_injection(
    mock_renderer: EmailTemplateRenderer,
    monkeypatch: pytest.MonkeyPatch,
):
    """Verifies successful rendering of both text and HTML templates with context."""
    # Arrange
    fake_settings = type(
        "Settings",
        (),
        {
            "DOMAIN_URL": "https://app.aegis-erp.com/",
            "SUPPORT_EMAIL": "help@aegis-erp.com",
        },
    )()
    monkeypatch.setattr(
        "src.erp.services.emails.renderer.get_settings",
        lambda: fake_settings,
    )

    context = {"user_name": "Alice"}
    expected_year = str(datetime.now(UTC).year)

    # Act
    text_output, html_output = mock_renderer.render("welcome", context)

    # Assert
    assert "Hello Alice," in text_output
    assert "Welcome to https://app.aegis-erp.com!" in text_output  # Trailing slash stripped
    assert "Contact us at help@aegis-erp.com." in text_output
    assert f"Copyright {expected_year}." in text_output

    # HTML template assertions
    assert "<h1>Hello Alice</h1>" in html_output
    assert '<a href="https://app.aegis-erp.com">Home</a>' in html_output
    assert "<p>Support: help@aegis-erp.com</p>" in html_output
    assert f"<footer>{expected_year}</footer>" in html_output


def test_render_default_fallback_settings(
    mock_renderer: EmailTemplateRenderer,
    monkeypatch: pytest.MonkeyPatch,
):
    """Verifies fallback values when DOMAIN_URL or SUPPORT_EMAIL are not present on settings."""
    # Arrange: empty settings object lacking optional attributes
    fake_settings = type("Settings", (), {})()
    monkeypatch.setattr(
        "src.erp.services.emails.renderer.get_settings",
        lambda: fake_settings,
    )

    # Act
    text_output, _html_output = mock_renderer.render("welcome", {"user_name": "Bob"})

    # Assert
    assert "Welcome to !" in text_output
    assert "Contact us at erp.aegis@gmail.com." in text_output


def test_context_override_defaults(
    mock_renderer: EmailTemplateRenderer,
    monkeypatch: pytest.MonkeyPatch,
):
    """Verifies user-provided context variables can override standard default variables."""
    # Arrange
    fake_settings = type("Settings", (), {"DOMAIN_URL": "http://localhost:5173"})()
    monkeypatch.setattr(
        "src.erp.services.emails.renderer.get_settings",
        lambda: fake_settings,
    )

    override_context = {
        "user_name": "Charlie",
        "support_email": "custom_support@example.com",
        "current_year": 2099,
    }

    # Act
    text_output, _ = mock_renderer.render("welcome", override_context)

    # Assert
    assert "Contact us at custom_support@example.com." in text_output
    assert "Copyright 2099." in text_output


def test_html_autoescaping(temp_templates_dir: Path):
    """Verifies HTML template auto-escaping works to prevent XSS."""
    # Arrange
    html_content = "<p>User input: {{ malicious_input }}</p>"
    (temp_templates_dir / "security.html.j2").write_text(html_content, encoding="utf-8")
    (temp_templates_dir / "security.txt.j2").write_text("plain text", encoding="utf-8")

    renderer = EmailTemplateRenderer(templates_dir=temp_templates_dir)
    context = {"malicious_input": "<script>alert(1)</script>"}

    # Act
    _, html_output = renderer.render("security", context)

    # Assert
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_output
    assert "<script>" not in html_output


def test_render_missing_template_raises_error(mock_renderer: EmailTemplateRenderer):
    """Verifies TemplateNotFound exception is raised when template files do not exist."""
    with pytest.raises(TemplateNotFound):
        mock_renderer.render("non_existent_template", {})


def test_global_renderer_instance():
    """Verifies global module instance initialized correctly."""
    assert isinstance(renderer, EmailTemplateRenderer)
    assert renderer.env.autoescape is True
