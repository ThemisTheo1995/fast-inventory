from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.erp.core.config import get_settings

settings = get_settings()

engine_kwargs = {
    "pool_pre_ping": True,
    "echo": False
}

if settings.ENVIRONMENT in ("production", "staging"):
    engine_kwargs.update(
        {
            "pool_size": 1,
            "max_overflow": 2,
            "pool_recycle": 300,
            "pool_timeout": 5,
        }
    )

# Create the engine
engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Base model
class Base(DeclarativeBase):
    pass


# Database Dependency for FastAPI routes
def get_db() -> Generator[Session, Any]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
