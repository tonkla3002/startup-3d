"""Async engine + session factory."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_settings = get_settings()

engine = create_async_engine(
    _settings.database_url or "postgresql+asyncpg://localhost/streamora",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=5,
)

AsyncSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, autoflush=False, class_=AsyncSession
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency — session ใหม่ต่อ 1 request."""
    async with AsyncSessionLocal() as session:
        yield session
