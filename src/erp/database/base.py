from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from erp.core.config import get_settings

settings = get_settings()

engine_kwargs = {
    "pool_pre_ping": True,
}

if settings.ENVIRONMENT == "prod":
    engine_kwargs.update({
        "pool_size": 20,
        "max_overflow": 10,
        "echo": False,
    })
else:
    engine_kwargs.update({
        "echo": False,
    })

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
