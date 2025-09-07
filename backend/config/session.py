"""
Database session management for SQLModel with AsyncPG.
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from .database import db_config


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get database session.

    Yields:
        AsyncSession: Database session for database operations
    """
    async with db_config.async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_session_context() -> AsyncSession:
    """
    Get database session as context manager.

    Returns:
        AsyncSession: Database session for database operations
    """
    return db_config.async_session_factory()
