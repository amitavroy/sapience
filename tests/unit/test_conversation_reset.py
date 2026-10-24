from contextlib import asynccontextmanager
from functools import partial

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.agent import graph as graph_module
from app.agent.graph import build_graph
from app.services import conversation, conversation_queue
from app.services.conversation_queue import QueueItem
from app.services.google_chat import FAILURE_REPLY, RESET_REPLY
from tests.agent_helpers import FakeChat, FakeChatModel, FakeRedis, NullLog

SPACE = "spaces/A"


def item(user: str, n: int, text: str = "", kind: str = "message", space: str = SPACE) -> QueueItem:
    return QueueItem(
        kind=kind,
        space=space,
        user=user,
        message_name=f"{space}/messages/{user}-{n}",
        text=text,
        display_name=user,
    )


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> FakeChatModel:
    fake = FakeChatModel(replies=["r1", "r2", "r3", "r4", "r5", "r6"], calls=[])
    monkeypatch.setattr(graph_module, "get_model", lambda role: fake)
    return fake


@pytest.fixture
def saver(monkeypatch: pytest.MonkeyPatch, model: FakeChatModel) -> InMemorySaver:
    """One in-memory checkpointer behind both the graph and the reset."""
    shared = InMemorySaver()

    @asynccontextmanager
    async def open_checkpointer():
        yield shared

    @asynccontextmanager
    async def open_graph():
        yield build_graph(shared)

    monkeypatch.setattr(conversation, "open_checkpointer", open_checkpointer)
    monkeypatch.setattr(conversation, "open_graph", open_graph)
    return shared


async def drain(chat: FakeChat, redis: FakeRedis, user: str, *items: QueueItem) -> None:
    for queued in items:
        await conversation_queue.enqueue(redis, queued)
    await conversation_queue.drain(
        redis, items[0].space, user, partial(conversation.process_item, chat, NullLog())
    )


def texts(call: list) -> list[str]:
    return [m.text for m in call]


async def test_reset_clears_memory_and_keeps_the_order(
    saver: InMemorySaver, model: FakeChatModel
) -> None:
    chat, redis = FakeChat(), FakeRedis()

    await drain(
        chat,
        redis,
        "users/1",
        item("users/1", 1, "my name is Ana"),
        item("users/1", 2, kind="reset"),
        item("users/1", 3, "what is my name?"),
    )

    # the message before the reset is answered first, then cleared, then a fresh start
    assert [text for _, text in chat.sent] == ["r1", RESET_REPLY, "r2"]
    assert "my name is Ana" not in texts(model.calls[1])
    assert texts(model.calls[1])[-1] == "what is my name?"


async def test_reset_leaves_other_users_and_spaces_alone(
    saver: InMemorySaver, model: FakeChatModel
) -> None:
    chat, redis = FakeChat(), FakeRedis()
    await drain(chat, redis, "users/2", item("users/2", 1, "bob here"))
    await drain(chat, redis, "users/1", item("users/1", 1, "ann here", space="spaces/B"))
    await drain(chat, redis, "users/1", item("users/1", 2, "ann in A"))

    await drain(chat, redis, "users/1", item("users/1", 3, kind="reset"))
    await drain(chat, redis, "users/2", item("users/2", 2, "who am I?"))

    assert "bob here" in texts(model.calls[-1])
    assert (
        await saver.aget_tuple({"configurable": {"thread_id": "gchat:spaces/B:users/1"}})
        is not None
    )
    assert await saver.aget_tuple({"configurable": {"thread_id": "gchat:spaces/A:users/1"}}) is None


async def test_failed_reset_posts_the_apology_and_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def broken_checkpointer():
        raise ConnectionError("database down")
        yield

    monkeypatch.setattr(conversation, "open_checkpointer", broken_checkpointer)
    chat = FakeChat()

    await conversation.process_item(chat, NullLog(), item("users/1", 1, kind="reset"))

    assert chat.sent == [(SPACE, FAILURE_REPLY)]
