from unittest.mock import MagicMock

import pytest
from google.genai import types

from erp.services.ai.embedding import generate_embedding


def test_generate_embedding_success(mock_genai_client):
    """Verifies that generate_embedding returns vector values and calls GenAI SDK with expected arguments."""
    mock_client_cls, mock_instance = mock_genai_client

    # Build mock response matching google.genai response structure
    expected_vector = [0.123] * 768
    mock_embedding = MagicMock()
    mock_embedding.values = expected_vector

    mock_response = MagicMock()
    mock_response.embeddings = [mock_embedding]

    mock_instance.models.embed_content.return_value = mock_response

    input_text = "Enterprise Resource Planning"

    # Act
    result = generate_embedding(input_text)

    # Assert return value
    assert result == expected_vector
    assert len(result) == 768

    # Assert Client initialization
    mock_client_cls.assert_called_once_with(api_key="test-key-123")

    # Assert embed_content arguments
    mock_instance.models.embed_content.assert_called_once()
    _, kwargs = mock_instance.models.embed_content.call_args

    assert kwargs["model"] == "gemini-embedding-001"
    assert kwargs["contents"] == input_text
    assert isinstance(kwargs["config"], types.EmbedContentConfig)
    assert kwargs["config"].output_dimensionality == 768


def test_generate_embedding_api_failure(mock_genai_client):
    """Verifies exception propagation when the GenAI client call raises an exception."""
    _, mock_instance = mock_genai_client

    # Simulate API failure (e.g., rate limit or network error)
    mock_instance.models.embed_content.side_effect = RuntimeError("API connection failed")

    with pytest.raises(RuntimeError, match="API connection failed"):
        generate_embedding("Test payload")


def test_generate_embedding_empty_input(mock_genai_client):
    """Verifies behavior when given an empty string."""
    _, mock_instance = mock_genai_client

    mock_embedding = MagicMock()
    mock_embedding.values = [0.0] * 768
    mock_response = MagicMock()
    mock_response.embeddings = [mock_embedding]

    mock_instance.models.embed_content.return_value = mock_response

    result = generate_embedding("")

    assert len(result) == 768
    mock_instance.models.embed_content.assert_called_once()
    assert mock_instance.models.embed_content.call_args.kwargs["contents"] == ""
