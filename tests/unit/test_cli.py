import asyncio

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from typer.testing import CliRunner

from app.cli import __main__ as cli
from app.db.base import Base
from app.services import user as user_service

ARGS = ["seed-user", "--email", "Seed@Example.com", "--password", "seedpass123"]


def test_check_db() -> None:
    result = CliRunner().invoke(cli.app, ["check-db"])

    assert result.exit_code == 0
    assert "database ok" in result.output


@pytest.fixture
def factory(monkeypatch: pytest.MonkeyPatch) -> async_sessionmaker:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)

    async def create_tables() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(create_tables())
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(cli, "async_session_factory", factory)
    monkeypatch.setattr(cli.settings, "debug", True)
    return factory


def test_seed_user_creates_then_is_idempotent(factory: async_sessionmaker) -> None:
    runner = CliRunner()
    first = runner.invoke(cli.app, ARGS)
    second = runner.invoke(cli.app, ARGS)

    assert first.exit_code == 0
    assert "user created" in first.output
    assert second.exit_code == 0
    assert "user exists" in second.output

    async def authenticate():
        async with factory() as db:
            return await user_service.authenticate(db, "seed@example.com", "seedpass123")

    assert asyncio.run(authenticate()) is not None


def test_seed_user_refuses_without_debug(
    factory: async_sessionmaker, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli.settings, "debug", False)
    runner = CliRunner()

    refused = runner.invoke(cli.app, ARGS)
    forced = runner.invoke(cli.app, [*ARGS, "--force"])

    assert refused.exit_code != 0
    assert "DEBUG" in refused.output
    assert forced.exit_code == 0
