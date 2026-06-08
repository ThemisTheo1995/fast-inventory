import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from alembic import command
from erp.core.config import get_settings
from erp.database.base import get_db
from erp.main import app
from erp.model_registry import metadata as target_metadata

settings = get_settings()

if not hasattr(settings, "TEST_DATABASE_URL") or not settings.TEST_DATABASE_URL:
    msg = "CRITICAL: TEST_DATABASE_URL is missing from your environment configuration!"
    raise ValueError(msg)

engine = create_engine(settings.TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(bind=engine)


@pytest.fixture(scope="session", autouse=True)
def initialize_test_db():
    """
    Applies Alembic migrations to build the test DB, ensuring it matches
    production exactly, then drops everything after the test session.
    """
    # Point Alembic to the Test DB and upgrade to latest
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", str(settings.TEST_DATABASE_URL))
    command.upgrade(alembic_cfg, "head")

    yield

    with engine.begin() as connection:
        # Instantly drops tables in correct topological order
        target_metadata.drop_all(bind=connection)
        # Removes the Alembic tracker so the next test run starts fresh
        connection.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE;"))


@pytest.fixture
def db_session():
    """Provides a fresh transaction that forces a rollback after every test, even if commit() was called."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """Overrides the DB dependency and yields the standard TestClient."""
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()
