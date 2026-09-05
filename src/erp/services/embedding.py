from google import genai
from google.genai import types

from erp.core.config import get_settings

settings = get_settings()


def generate_embedding(text: str) -> list[float]:
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    response = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=768),
    )
    return response.embeddings[0].values
