from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.erp.core.config import get_settings

settings = get_settings()

engine_kwargs: dict[str, Any] = {
    "pool_pre_ping": True,
    "echo": False,
    "connect_args": {"server_settings": {"timezone": "utc"}},
}

if settings.ENVIRONMENT in ("production", "staging"):
    engine_kwargs.update({"pool_size": 10, "max_overflow": 20, "pool_recycle": 300, "pool_timeout": 30, "echo": False})

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# Base model
class Base(DeclarativeBase):
    pass


# Database Dependency for FastAPI routes
async def get_db() -> AsyncGenerator[AsyncSession]:
    async with AsyncSessionLocal() as db:
        yield db
