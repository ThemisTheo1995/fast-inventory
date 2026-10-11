import json
import logging
import os
from functools import lru_cache
from pathlib import Path

from boto3.session import Session
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent

IS_TESTING = os.getenv("TESTING", "false").lower() in ("true", "1", "t", "yes")
ENV_FILE = None if IS_TESTING else (ROOT_DIR / ".env")


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/erp_test"
    TEST_DATABASE_URL: str | None = None

    # Domain URLs
    DOMAIN_URL: str = "http://localhost:5173"

    # Auth
    AUTH_SECRET_KEY: str = "dev-insecure-secret-key-change-in-prod-1234567890"
    AUTH_ALGORITHM: str = "HS256"
    AUTH_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    AUTH_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Tokens cooldown
    PASSWORD_RESET_COOLDOWN_MINUTES: int = 5
    CHANGE_EMAIL_COOLDOWN_MINUTES: int = 5

    # Cookies
    COOKIE_SECURE: int = 0

    # GEMINI
    GEMINI_API_KEY: str | None = None
    GEMINI_API_KEY_NAME: str | None = None

    # Email
    DEFAULT_FROM_EMAIL: str = "noreply@example.com"
    SUPPORT_EMAIL: str = "support@example.com"
    EMAIL_PROVIDER: str = "console"

    # AWS
    AWS_REGION: str = "eu-west-1"
    BARCODE_GENERATION_SQS_QUEUE_URL: str | None = None
    AWS_SECRET_NAME: str | None = None

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


def _fetch_aws_secrets() -> dict[str, str]:
    """Fetches configuration secrets stored as a JSON string from AWS Secrets Manager."""
    secret_name = os.getenv("AWS_SECRET_NAME", None)

    if not secret_name:
        return {}

    region_name = os.getenv("AWS_REGION", "eu-west-1")

    try:
        session = Session()
        client = session.client(
            service_name="secretsmanager",
            region_name=region_name,
        )
        response = client.get_secret_value(SecretId=secret_name)

        if "SecretString" in response:
            return json.loads(response["SecretString"])
    except (ClientError, BotoCoreError, json.JSONDecodeError) as err:
        logger.warning(
            "AWS Secrets Manager fetch failed (%s). Falling back to environment/default values.", err
        )

    return {}


@lru_cache
def get_settings() -> Settings:

    if IS_TESTING:
        return Settings()

    if ENV_FILE and ENV_FILE.exists():
        load_dotenv(ENV_FILE)

    aws_secrets = _fetch_aws_secrets()

    return Settings(**aws_secrets)
