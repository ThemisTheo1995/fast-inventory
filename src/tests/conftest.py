from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from src.erp.api.modules.inventory.handlers import register_inventory_handlers
from src.erp.core.config import get_settings
from src.erp.core.event_bus import EventBus
from src.erp.database.base import get_db
from src.erp.main import app
from src.erp.model_registry import metadata as target_metadata

settings = get_settings()

TEST_DATABASE_URL = settings.TEST_DATABASE_URL

if not TEST_DATABASE_URL:
    msg = "CRITICAL: TEST_DATABASE_URL is missing from your environment configuration!"
    raise ValueError(msg)

# ---------------------------------------------------------------------------
# Core Pytest Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def initialize_test_db() -> Generator[None]:
    """
    Applies Alembic migrations before tests run and drops tables afterward.
    This uses a synchronous engine, so it is immune to async loop mismatches.
    """
    sync_database_url = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", sync_database_url)

    # 1. Migrate up
    command.upgrade(alembic_cfg, "head")

    yield

    # 2. Teardown down
    sync_engine = create_engine(sync_database_url, connect_args={"options": "-c timezone=utc"})
    with sync_engine.begin() as connection:
        target_metadata.drop_all(bind=connection)
        connection.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))

    sync_engine.dispose()


@pytest_asyncio.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine]:
    """
    Function-scoped AsyncEngine.
    This guarantees the engine and asyncpg connections are bound strictly to the
    exact same event loop as the test that is currently running.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"server_settings": {"timezone": "UTC"}},
        poolclass=NullPool,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """
    Provides an isolated, transaction-bound AsyncSession.
    App-level db.commit() calls will create savepoints, allowing rollback after the test.
    """
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
    """
    HTTP client for testing FastAPI router endpoints.
    Overrides the get_db dependency to use the isolated test transaction.
    """

    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def event_bus() -> EventBus:
    """Provides a fresh EventBus."""
    bus = EventBus()
    register_inventory_handlers(bus)
    return bus


@pytest.fixture(autouse=True)
def mock_generate_embedding(monkeypatch):
    """Returns a dummy vector array instead of making a network request."""

    def fake_embed(text: str) -> list[float]:  # noqa
        return [0.123] * 768

    monkeypatch.setattr("src.erp.services.embedding.generate_embedding", fake_embed)
