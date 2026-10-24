from contextlib import asynccontextmanager

import pytest

from app.agent.state import ConversationContext
from app.core.celery_app import celery_app
from app.core.logger import logger
from app.core.trace import trace_id as trace_var
from app.services import conversation, conversation_queue
from app.services.conversation_queue import QueueItem
from app.services.google_chat import FAILURE_REPLY
from app.tasks import conversation as conversation_task
from tests.agent_helpers import FakeChat, FakeGraph, NullLog

ITEM = QueueItem(
    space="spaces/A",
    user="users/1",
    message_name="spaces/A/messages/1",
    text="hi",
    display_name="Ann",
)


@pytest.fixture
def logs() -> list[dict]:
    records: list[dict] = []
    sink = logger.add(lambda m: records.append(m.record), level="INFO")
    yield records
    logger.remove(sink)


@pytest.fixture(autouse=True)
def fake_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    @asynccontextmanager
    async def open_graph():
        yield FakeGraph()

    monkeypatch.setattr(conversation, "open_graph", open_graph)


@pytest.fixture
def turns(monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """(ctx, message_name, text) for every turn the fake graph ran."""
    calls: list[tuple] = []

    async def run_turn(
        graph, ctx: ConversationContext, message_name: str, text: str, from_checkpoint=None
    ) -> str:
        calls.append((ctx, message_name, text))
        return "reply"

    monkeypatch.setattr(conversation, "run_turn", run_turn)
    return calls


async def test_message_item_runs_a_turn_and_posts_the_reply(turns: list[tuple]) -> None:
    chat = FakeChat()

    await conversation.process_item(chat, NullLog(), ITEM)

    [(ctx, message_name, text)] = turns
    assert (ctx.space, ctx.user, ctx.display_name) == ("spaces/A", "users/1", "Ann")
    assert (message_name, text) == ("spaces/A/messages/1", "hi")
    assert chat.sent == [("spaces/A", "reply")]


async def test_failed_turn_posts_the_apology(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(graph, ctx, message_name, text, from_checkpoint=None) -> str:
        raise RuntimeError("model down")

    monkeypatch.setattr(conversation, "run_turn", boom)
    chat = FakeChat()

    await conversation.process_item(chat, NullLog(), ITEM)

    assert chat.sent == [("spaces/A", FAILURE_REPLY)]


async def test_failed_apology_is_logged_not_raised(
    monkeypatch: pytest.MonkeyPatch, logs: list[dict]
) -> None:
    async def boom(graph, ctx, message_name, text, from_checkpoint=None) -> str:
        raise RuntimeError("model down")

    monkeypatch.setattr(conversation, "run_turn", boom)
    chat = FakeChat()

    async def chat_down(space: str, text: str) -> str:
        raise RuntimeError("chat down")

    monkeypatch.setattr(chat, "create_message", chat_down)

    await conversation.process_item(chat, NullLog(), ITEM)

    assert chat.sent == []
    assert any("could not post the failure reply" in r["message"] for r in logs)


async def test_unsupported_item_kind_is_skipped_with_a_warning(
    turns: list[tuple], logs: list[dict]
) -> None:
    chat = FakeChat()

    await conversation.process_item(chat, NullLog(), ITEM.model_copy(update={"kind": "bogus"}))

    assert turns == []
    assert chat.sent == []
    assert any("unsupported queue item kind=bogus" in r["message"] for r in logs)


async def test_graph_that_cannot_be_opened_still_gets_the_apology(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # e.g. LLM_API_KEY unset: build_graph raises ConversationError
    @asynccontextmanager
    async def broken_graph():
        raise RuntimeError("no key")
        yield

    monkeypatch.setattr(conversation, "open_graph", broken_graph)
    chat = FakeChat()

    await conversation.process_item(chat, NullLog(), ITEM)

    assert chat.sent == [("spaces/A", FAILURE_REPLY)]


async def test_drain_runs_the_queued_items_through_process_item(
    monkeypatch: pytest.MonkeyPatch, turns: list[tuple]
) -> None:
    chat, drained = FakeChat(), []

    @asynccontextmanager
    async def open_redis():
        yield "redis"

    @asynccontextmanager
    async def open_chat_client():
        yield chat

    async def queue_drain(redis, space, user, process) -> None:
        drained.append((redis, space, user))
        await process(ITEM)

    monkeypatch.setattr(conversation_queue, "open_redis", open_redis)
    monkeypatch.setattr(conversation.google_chat_service, "open_chat_client", open_chat_client)
    monkeypatch.setattr(conversation_queue, "drain", queue_drain)

    await conversation.drain("spaces/A", "users/1", NullLog())

    assert drained == [("redis", "spaces/A", "users/1")]
    assert chat.sent == [("spaces/A", "reply")]


def test_task_drains_under_its_trace_id_and_resets_it(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple] = []

    async def fake_drain(space: str, user: str, log) -> None:
        seen.append((space, user, trace_var.get()))

    monkeypatch.setattr(conversation_task.conversation_service, "drain", fake_drain)
    before = trace_var.get()

    conversation_task.drain_conversation("spaces/A", "users/1", "trace1234")

    assert seen == [("spaces/A", "users/1", "trace1234")]
    assert trace_var.get() == before


def test_task_resets_the_trace_id_when_the_drain_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing_drain(space: str, user: str, log) -> None:
        raise RuntimeError("redis down")

    monkeypatch.setattr(conversation_task.conversation_service, "drain", failing_drain)
    before = trace_var.get()

    with pytest.raises(RuntimeError):
        conversation_task.drain_conversation("spaces/A", "users/1", "trace1234")

    assert trace_var.get() == before


def test_drain_task_is_registered_with_celery() -> None:
    assert "app.tasks.conversation" in celery_app.conf.include
