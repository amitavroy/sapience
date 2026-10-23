from sqlalchemy.ext.asyncio import AsyncSession

from app.services import health as health_service


async def test_ping_db_runs_on_session(db_session: AsyncSession) -> None:
    await health_service.ping_db(db_session)  # must not raise
