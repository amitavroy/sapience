from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

engine = create_async_engine(settings.database_url)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def task_session() -> AsyncIterator[AsyncSession]:
    """Session for Celery tasks. Each task runs in its own event loop (asyncio.run), and a
    pooled engine is bound to the loop that created it, so use a throwaway NullPool engine."""
    task_engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        async with async_sessionmaker(task_engine, expire_on_commit=False)() as session:
            yield session
    finally:
        await task_engine.dispose()
