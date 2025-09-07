"""
Database configuration for SQLModel with AsyncPG.
"""

import os
import logging
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


class DatabaseConfig:
    """Database configuration class."""

    def __init__(self):
        self.database_url: str = self._get_database_url()
        self.engine = self._create_engine()
        self.async_session_factory = self._create_session_factory()

    def _get_database_url(self) -> str:
        """Get database URL from individual PostgreSQL environment variables."""
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        user = os.getenv("POSTGRES_USER", "sapience_user")
        password = os.getenv("POSTGRES_PASSWORD", "sapience_password")
        db_name = os.getenv("POSTGRES_DB", "sapience_db")

        database_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db_name}"
        logger.info(
            f"Database URL constructed: postgresql+asyncpg://{user}:***@{host}:{port}/{db_name}"
        )

        return database_url

    def _create_engine(self):
        """Create async engine for database connections."""
        return create_async_engine(
            self.database_url,
            echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
            future=True,
            pool_pre_ping=True,
            pool_recycle=300,
        )

    def _create_session_factory(self):
        """Create async session factory."""
        return sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def create_tables(self):
        """Create all tables defined in SQLModel."""
        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    async def close(self):
        """Close the database engine."""
        await self.engine.dispose()


# Global database configuration instance
db_config = DatabaseConfig()
