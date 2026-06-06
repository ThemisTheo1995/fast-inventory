import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from erp.core.config import get_settings
from erp.database.base import Base, get_db
from erp.main import app

settings = get_settings()

# 🎯 Guardrail: Ensure the dedicated test database string is present
if not hasattr(settings, "TEST_DATABASE_URL") or not settings.TEST_DATABASE_URL:
    raise ValueError(
        "CRITICAL: TEST_DATABASE_URL is missing from your environment configuration!"
    )

engine = create_engine(settings.TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(bind=engine)


@pytest.fixture(scope="session", autouse=True)
def initialize_test_db():
    """
    Safely verifies the schema structures, creates missing tables,
    and empties all row records upon test suite completion.
    """
    Base.metadata.create_all(bind=engine)

    yield

    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())


@pytest.fixture
def db_session():
    """Provides a fresh transaction that rolls back after every single test."""
    session = TestingSessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def client(db_session):
    """Overrides the DB dependency and yields the standard TestClient."""
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()
