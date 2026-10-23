import asyncio

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from typer.testing import CliRunner

from app.cli import __main__ as cli
from app.db.base import Base
from app.models.chunk import Chunk
from app.models.collection import Collection, CollectionMember
from app.models.document import Document
from app.services import user as user_service

ARGS = ["seed-user", "--email", "Seed@Example.com", "--password", "seedpass123"]


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


def test_check_db(factory: async_sessionmaker, monkeypatch: pytest.MonkeyPatch) -> None:
    pinged: list[AsyncSession] = []

    async def ping_db(db: AsyncSession) -> None:
        pinged.append(db)

    monkeypatch.setattr(cli.health_service, "ping_db", ping_db)

    result = CliRunner().invoke(cli.app, ["check-db"])

    assert result.exit_code == 0
    assert "database ok" in result.output
    assert len(pinged) == 1


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


def fetch_all(factory: async_sessionmaker, model):
    async def run():
        async with factory() as db:
            return list((await db.scalars(select(model))).all())

    return asyncio.run(run())


def test_create_collection_prints_the_id(factory: async_sessionmaker) -> None:
    result = CliRunner().invoke(
        cli.app, ["create-collection", "Docs", "--description", "Python docs"]
    )

    assert result.exit_code == 0
    [collection] = fetch_all(factory, Collection)
    assert f"collection created: {collection.id} (Docs)" in result.output
    assert collection.description == "Python docs"
    assert fetch_all(factory, CollectionMember) == []


def test_create_collection_with_unknown_owner_exits_1(factory: async_sessionmaker) -> None:
    result = CliRunner().invoke(
        cli.app, ["create-collection", "Docs", "--owner-email", "nobody@example.com"]
    )

    assert result.exit_code == 1
    assert "nobody@example.com not found" in result.output
    assert fetch_all(factory, Collection) == []


def test_create_collection_with_owner_adds_an_owner_membership(
    factory: async_sessionmaker,
) -> None:
    runner = CliRunner()
    runner.invoke(cli.app, ARGS)

    result = runner.invoke(
        cli.app, ["create-collection", "Docs", "--owner-email", "seed@example.com"]
    )

    assert result.exit_code == 0
    [collection] = fetch_all(factory, Collection)
    [member] = fetch_all(factory, CollectionMember)
    assert member.collection_id == collection.id
    assert member.role == "owner"
    assert collection.created_by_id == member.user_id


def add_document_with_chunks(factory: async_sessionmaker) -> int:
    async def run() -> int:
        async with factory() as db:
            collection = Collection(name="Docs")
            db.add(collection)
            await db.flush()
            document = Document(collection_id=collection.id, title="T", content_hash="h")
            # stored out of order: show-chunks must print in chunk_index order
            document.chunks = [
                Chunk(
                    collection_id=collection.id,
                    chunk_index=i,
                    content=f"body {i}",
                    token_count=10 + i,
                    meta={"heading_path": ["Guide", "Install"] if i == 0 else []},
                )
                for i in (1, 0)
            ]
            db.add(document)
            await db.commit()
            return document.id

    return asyncio.run(run())


def test_show_chunks_prints_chunks_in_order(factory: async_sessionmaker) -> None:
    document_id = add_document_with_chunks(factory)

    result = CliRunner().invoke(cli.app, ["show-chunks", str(document_id)])

    assert result.exit_code == 0
    assert result.output.index("chunk 0 | 10 tokens | Guide > Install") < result.output.index(
        "chunk 1 | 11 tokens | (no heading)"
    )
    assert "body 0" in result.output and "body 1" in result.output
    assert "2 chunks" in result.output


def test_show_chunks_exits_1_for_an_unknown_document(factory: async_sessionmaker) -> None:
    result = CliRunner().invoke(cli.app, ["show-chunks", "999"])

    assert result.exit_code == 1
    assert "document 999 not found" in result.output
