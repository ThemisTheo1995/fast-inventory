from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_genai_client(monkeypatch):
    """Mocks get_settings and genai.Client to isolate external dependencies."""
    fake_settings = type("Settings", (), {"GEMINI_API_KEY": "test-key-123"})()
    monkeypatch.setattr(
        "erp.services.ai.embedding.settings",
        fake_settings,
    )

    with patch("erp.services.ai.embedding.genai.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_client_cls.return_value = mock_instance
        yield mock_client_cls, mock_instance
