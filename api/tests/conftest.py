import os

# Settings and the storage client are instantiated at import time, so populate
# the environment with throwaway values before any undocking_api module is imported.
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("R2_ACCOUNT_ID", "test-account")
os.environ.setdefault("R2_ACCESS_KEY_ID", "test-key-id")
os.environ.setdefault("R2_SECRET_ACCESS_KEY", "test-secret")
os.environ.setdefault("R2_BUCKET_NAME", "test-bucket")
os.environ.setdefault("R2_PUBLIC_URL", "https://artifacts.test")
os.environ.setdefault("PUBLIC_BASE_URL", "http://testserver")

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from undocking_api.models import Base


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    """Provides a session backed by a fresh in-memory SQLite database per test."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()
