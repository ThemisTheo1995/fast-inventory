from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"  # expected: "development", "production", or "test"

    # Database
    DATABASE_URL: str
    TEST_DATABASE_URL: str | None = None

    # Auth
    AUTH_SECRET_KEY: str
    AUTH_ALGORITHM: str
    AUTH_ACCESS_TOKEN_EXPIRE_MINUTES: int
    AUTH_REFRESH_TOKEN_EXPIRE_DAYS: int

    # Cookies
    COOKIE_SECURE: int

    # AI
    GEMINI_API_KEY: str

    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
