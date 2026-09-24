# ruff: noqa: E402

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
TEST_ENV_FILE = ROOT_DIR / ".env.test"

if TEST_ENV_FILE.exists():
    load_dotenv(TEST_ENV_FILE, override=True)

fallback_db = "postgresql+psycopg://postgres:postgres@localhost:5432/test_db"
db_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL") or fallback_db

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("TEST_DATABASE_URL", db_url)
os.environ.setdefault("DATABASE_URL", db_url)
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

os.environ.setdefault("AUTH_SECRET_KEY", "testing")
os.environ.setdefault("AUTH_ALGORITHM", "TESTALGO")
os.environ.setdefault("AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", "5")
os.environ.setdefault("AUTH_REFRESH_TOKEN_EXPIRE_DAYS", "7")
os.environ.setdefault("COOKIE_SECURE", "1")

os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "eu-west-1")
os.environ.setdefault("AWS_REGION", "eu-west-1")
os.environ.setdefault("DEFAULT_FROM_EMAIL", "sender@example.com")
os.environ.setdefault("EMAIL_PROVIDER", "ses")
os.environ.setdefault("SUPPORT_EMAIL", "sender@example.com")


import asyncio
from collections.abc import AsyncGenerator, Generator

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

from src.erp.api.modules.inventory.handlers import register_inventory_handlers
from src.erp.core.config import Settings, get_settings
from src.erp.core.event_bus import EventBus
from src.erp.database.base import get_db
from src.erp.main import app
from src.erp.model_registry import metadata as target_metadata

get_settings.cache_clear()


# ==============================================================================
# 2. FIXTURES
# ==============================================================================


@pytest.fixture(scope="session", autouse=True)
def global_mock_aws() -> Generator[None]:
    """Session-scoped AWS mock intercepting all boto3/botocore calls globally.

    Verifies default sender email ONCE at startup to avoid per-test Moto initialization.
    """
    with mock_aws():
        client = boto3.client("ses", region_name="eu-west-1")
        client.verify_email_identity(EmailAddress=os.environ.get("DEFAULT_FROM_EMAIL", "sender@example.com"))
        yield


@pytest.fixture(scope="session")
def ses_client() -> boto3.client:
    """Session-scoped boto3 client. Prevents botocore from re-parsing JSON specs per test."""
    return boto3.client("ses", region_name="eu-west-1")


@pytest.fixture
def settings() -> Settings:
    """Provides cached Settings instance to tests."""
    return get_settings()


def _get_test_database_url() -> str:
    """Helper to fetch and validate TEST_DATABASE_URL dynamically at runtime."""
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
async def db_session(
    db_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession]:
    """Function-scoped session with rollback isolation per test."""
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
async def client(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient]:
    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def event_bus() -> EventBus:
    """Session-scoped EventBus with pre-registered handlers."""
    bus = EventBus()
    register_inventory_handlers(bus)
    return bus


@pytest.fixture(autouse=True)
def mock_generate_embedding(monkeypatch):
    def fake_embed(text: str) -> list[float]:  # noqa
        return [0.123] * 768

    monkeypatch.setattr("src.erp.services.ai.embedding.generate_embedding", fake_embed)
