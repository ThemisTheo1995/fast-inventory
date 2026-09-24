import logging
import os
from functools import lru_cache
from pathlib import Path

from bitwarden_sdk import BitwardenClient, DeviceType, client_settings_from_dict
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent

IS_TESTING = os.getenv("TESTING", "false").lower() in ("true", "1", "t", "yes")
ENV_FILE = None if IS_TESTING else (ROOT_DIR / ".env")


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str
    TEST_DATABASE_URL: str | None = None

    # Domain URLs
    DOMAIN_URL: str = "http://localhost:5173"

    # Auth
    AUTH_SECRET_KEY: str | None = None
    AUTH_ALGORITHM: str | None = None
    AUTH_ACCESS_TOKEN_EXPIRE_MINUTES: int | None = None
    AUTH_REFRESH_TOKEN_EXPIRE_DAYS: int | None = None

    # Cookies
    COOKIE_SECURE: int | None = None

    # AI
    GEMINI_API_KEY: str | None = None
    GEMINI_API_KEY_NAME: str | None = None

    # Email
    DEFAULT_FROM_EMAIL: str | None = None
    SUPPORT_EMAIL: str | None = None
    EMAIL_PROVIDER: str | None = None

    # AWS
    AWS_REGION: str | None = None
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,  # Resolves to None during pytest execution
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    if ENV_FILE and ENV_FILE.exists():
        load_dotenv(ENV_FILE)

    bws_kwargs: dict[str, str] = {}

    if not IS_TESTING:
        bws_token = os.getenv("BWS_ACCESS_TOKEN")
        bws_project_id = os.getenv("BWS_PROJECT_ID")
        bws_org_id = os.getenv("BWS_ORG_ID")
        bws_api_url = os.getenv("BWS_API_URL", "https://api.bitwarden.eu")
        bws_identity_url = os.getenv("BWS_IDENTITY_URL", "https://identity.bitwarden.eu")

        if bws_token and bws_project_id and bws_org_id:
            try:
                client = BitwardenClient(
                    client_settings_from_dict(
                        {
                            "apiUrl": bws_api_url,
                            "deviceType": DeviceType.SDK,
                            "identityUrl": bws_identity_url,
                            "userAgent": "Python",
                        }
                    )
                )

                client.auth().login_access_token(bws_token)

                identifiers_response = client.secrets().list(bws_org_id)

                if identifiers_response.success and identifiers_response.data:
                    identifiers = getattr(
                        identifiers_response.data,
                        "data",
                        identifiers_response.data,
                    )
                    secret_ids = [s.id for s in identifiers]

                    if secret_ids:
                        secrets_response = client.secrets().get_by_ids(secret_ids)

                        if secrets_response.success and secrets_response.data:
                            secrets = getattr(
                                secrets_response.data,
                                "data",
                                secrets_response.data,
                            )
                            for secret in secrets:
                                bws_kwargs[secret.key] = secret.value

            except Exception as err:
                logger.warning(
                    "Bitwarden fetch skipped/failed (%s). Falling back to environment values.",
                    err,
                )

    return Settings(**bws_kwargs)
