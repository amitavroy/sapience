from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.core.config import settings


def conninfo() -> str:
    # psycopg wants a plain libpq URL; DATABASE_URL carries the SQLAlchemy driver suffix
    return settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


@asynccontextmanager
async def open_checkpointer() -> AsyncIterator[AsyncPostgresSaver]:
    async with AsyncPostgresSaver.from_conn_string(conninfo()) as saver:
        yield saver


async def setup_checkpointer() -> None:
    """Create or upgrade the checkpoint tables; idempotent."""
    async with open_checkpointer() as saver:
        await saver.setup()
