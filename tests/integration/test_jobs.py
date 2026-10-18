import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.schemas.user import UserCreate
from app.services import user as user_service
from app.tasks.user import _welcome_user


async def test_register_dispatches_welcome_job(
    client: httpx.AsyncClient, dispatched: list[tuple]
) -> None:
    response = await client.post(
        "/auth/register",
        json={"name": "Ann", "email": "ann@example.com", "password": "password123"},
    )

    assert response.status_code == 201
    assert dispatched == [("app.tasks.user.welcome_user", response.json()["id"])]


async def test_welcome_job_logs_for_existing_user(db_session: AsyncSession) -> None:
    user = await user_service.create_user(
        db_session, UserCreate(name="Ann", email="ann@example.com", password="password123")
    )
    messages: list[str] = []
    sink = logger.add(lambda m: messages.append(m.record["message"]), level="INFO")
    try:
        await _welcome_user(db_session, user.id)
    finally:
        logger.remove(sink)

    assert messages == ["welcome ann@example.com"]


async def test_welcome_job_ignores_missing_user(db_session: AsyncSession) -> None:
    await _welcome_user(db_session, 999)  # must not raise
