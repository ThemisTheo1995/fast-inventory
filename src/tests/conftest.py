# ruff: noqa: E402
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
TEST_ENV_FILE = ROOT_DIR / ".env.test"

if TEST_ENV_FILE.exists():
    load_dotenv(TEST_ENV_FILE, override=True)

test_db_url = os.environ.get("TEST_DATABASE_URL")
if not test_db_url:
    msg = "TEST_DATABASE_URL must be explicitly configured for tests. Refusing to run tests."
    raise RuntimeError(msg)

TEST_ENV_VARS = {
    "ENVIRONMENT": "testing",
    "TESTING": "true",
    "DATABASE_URL": test_db_url,
    "TEST_DATABASE_URL": test_db_url,
    "AUTH_SECRET_KEY": "testing-secret-key-at-least-32-bytes-long",
    "AUTH_ALGORITHM": "HS256",
    "AUTH_ACCESS_TOKEN_EXPIRE_MINUTES": "5",
    "AUTH_REFRESH_TOKEN_EXPIRE_DAYS": "7",
    "COOKIE_SECURE": "1",
    "AWS_SESSION_TOKEN": "testing",
    "AWS_DEFAULT_REGION": "eu-west-1",
    "AWS_REGION": "eu-west-1",
    "DEFAULT_FROM_EMAIL": "sender@example.com",
    "EMAIL_PROVIDER": "ses",
    "SUPPORT_EMAIL": "sender@example.com",
    "BARCODE_GENERATION_SQS_QUEUE_URL": "https://sqs.eu-west-1.amazonaws.com/123456789012/test-barcode-queue",
}

for key, value in TEST_ENV_VARS.items():
    os.environ.setdefault(key, value)

import asyncio
from collections.abc import AsyncGenerator, Generator
from unittest.mock import MagicMock

import boto3
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from moto import mock_aws
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from erp.api.modules.inventory.handlers import register_inventory_handlers
from erp.core.config import Settings, get_settings
from erp.core.event_bus import EventBus
from erp.database.base import get_db
from erp.main import app
from erp.model_registry import metadata as target_metadata

# ==============================================================================
# 2. FIXTURES
# ==============================================================================


@pytest.fixture(scope="session", autouse=True)
def global_mock_aws() -> Generator[None]:
    """Session-scoped AWS mock intercepting all boto3/botocore calls globally."""
    with mock_aws():
        # Setup SES
        ses = boto3.client("ses", region_name="eu-west-1")
        ses.verify_email_identity(EmailAddress=os.environ.get("DEFAULT_FROM_EMAIL", "sender@example.com"))

        # Setup SQS
        sqs = boto3.client("sqs", region_name="eu-west-1")
        queue = sqs.create_queue(QueueName="test-barcode-queue")
        # Barcode queue url
        os.environ["BARCODE_GENERATION_SQS_QUEUE_URL"] = queue["QueueUrl"]

        get_settings.cache_clear()

        yield


@pytest.fixture(scope="session")
def ses_client() -> boto3.client:
    return boto3.client("ses", region_name="eu-west-1")


@pytest.fixture
def settings() -> Settings:
    return get_settings()


def _get_test_database_url() -> str:
    test_url = get_settings().TEST_DATABASE_URL
    if not test_url:
        msg = "CRITICAL: TEST_DATABASE_URL is missing from your environment configuration!"
        raise ValueError(msg)
    return test_url


@pytest.fixture(scope="session", autouse=True)
def initialize_test_db() -> Generator[None]:
    """Applies Alembic migrations before tests run and drops tables afterward."""
    test_db_url = _get_test_database_url()

    database_url = make_url(test_db_url)
    sync_database_url = database_url.set(drivername="postgresql+psycopg")
    sync_engine = create_engine(sync_database_url, connect_args={"options": "-c timezone=UTC"})

    with sync_engine.begin() as connection:
        target_metadata.drop_all(bind=connection)
        connection.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", test_db_url)
    command.upgrade(alembic_cfg, "head")

    yield

    with sync_engine.begin() as connection:
        target_metadata.drop_all(bind=connection)
        connection.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))

    sync_engine.dispose()


@pytest.fixture(scope="session")
def db_engine(initialize_test_db) -> Generator[AsyncEngine]:  # noqa
    """Created ONCE globally, but safely used by function-scoped async tests."""
    url = _get_test_database_url()
    connect_args = {"options": "-c timezone=UTC"} if "psycopg" in url else {"server_settings": {"timezone": "UTC"}}

    engine = create_async_engine(
        url,
        connect_args=connect_args,
        poolclass=NullPool,
    )
    yield engine

    asyncio.run(engine.dispose())


@pytest_asyncio.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """Function-scoped session with rollback isolation per test. (Perfectly implemented)."""
    async with db_engine.connect() as connection:
        transaction = await connection.begin()

        testingsessionlocal = async_sessionmaker(
            bind=connection,
            class_=AsyncSession,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        async with testingsessionlocal() as session:
            yield session

        await transaction.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def event_bus() -> EventBus:
    bus = EventBus()
    register_inventory_handlers(bus)
    return bus


@pytest.fixture(scope="session", autouse=True)
def mock_genai_sdk() -> Generator[None]:
    mpatch = pytest.MonkeyPatch()

    mock_client = MagicMock()
    mock_embedding = MagicMock()
    mock_embedding.values = [0.123] * 768
    mock_client.models.embed_content.return_value = MagicMock(embeddings=[mock_embedding])

    mpatch.setattr("google.genai.Client", lambda **_kwargs: mock_client)

    yield

    mpatch.undo()
