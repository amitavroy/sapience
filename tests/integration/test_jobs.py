import asyncio
from contextlib import asynccontextmanager

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.schemas.user import UserCreate
from app.services import user as user_service
from app.tasks.user import welcome_user


async def test_register_dispatches_welcome_job(
    client: httpx.AsyncClient, dispatched: list[tuple]
) -> None:
    response = await client.post(
        "/auth/register",
        json={"name": "Ann", "email": "ann@example.com", "password": "password123"},
    )

    assert response.status_code == 201
    assert dispatched == [("app.tasks.user.welcome_user", response.json()["id"])]


@pytest.fixture(autouse=True)
def task_db(monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession) -> None:
    """Make the task's own session the test session."""

    @asynccontextmanager
    async def session():
        yield db_session

    monkeypatch.setattr("app.tasks.user.task_session", session)


async def test_welcome_job_logs_for_existing_user(db_session: AsyncSession) -> None:
    user = await user_service.create_user(
        db_session, UserCreate(name="Ann", email="ann@example.com", password="password123")
    )
    messages: list[str] = []
    sink = logger.add(lambda m: messages.append(m.record["message"]), level="INFO")
    try:
        # the task drives its own event loop, so run it off the test's loop
        await asyncio.to_thread(welcome_user, user.id)
    finally:
        logger.remove(sink)

    assert messages == ["welcome ann@example.com"]


async def test_welcome_job_ignores_missing_user() -> None:
    messages: list[str] = []
    sink = logger.add(lambda m: messages.append(m.record["message"]), level="WARNING")
    try:
        await asyncio.to_thread(welcome_user, 999)  # must not raise
    finally:
        logger.remove(sink)

    assert messages == ["welcome_user: user 999 not found"]
