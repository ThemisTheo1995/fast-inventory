from google import genai
from google.genai import types

from erp.core.config import get_settings

settings = get_settings()


client = genai.Client(api_key=settings.GEMINI_API_KEY)


def generate_embedding(text: str) -> list[float]:
    response = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=768),
    )
    return response.embeddings[0].values
