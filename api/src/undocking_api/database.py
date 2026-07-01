from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings

engine = create_async_engine(
    settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yields an async database session, closing it when the request finishes."""
    async with SessionLocal() as session:
        yield session
