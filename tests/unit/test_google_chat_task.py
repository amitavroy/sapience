import json
from contextlib import asynccontextmanager

import pytest

from app.core.logger import logger
from app.core.trace import trace_id as trace_var
from app.schemas.google_chat import ChatPayload
from app.services import conversation_queue, google_chat
from app.services.google_chat import DM_REPLY, EMPTY_REPLY, handle_event
from app.tasks.google_chat import process_chat_event
from tests.agent_helpers import FakeChat, FakeRedis
from tests.google_chat_helpers import CHAT_FIXTURES, SLASH_FIXTURE, click_event, load_fixture

SPACE, DM = CHAT_FIXTURES
DRAIN_TASK = "app.tasks.conversation.drain_conversation"


@pytest.fixture
def redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture(autouse=True)
def fake_chat(monkeypatch: pytest.MonkeyPatch, redis: FakeRedis) -> FakeChat:
    """No test reaches Google or Redis: the Chat client and the Redis client are fakes."""
    fake = FakeChat()

    @asynccontextmanager
    async def open_chat_client():
        yield fake

    @asynccontextmanager
    async def open_redis():
        yield redis

    monkeypatch.setattr(google_chat, "open_chat_client", open_chat_client)
    monkeypatch.setattr(conversation_queue, "open_redis", open_redis)
    return fake


@pytest.fixture
def logs() -> list[dict]:
    """Records of everything logged at INFO and above during the test."""
    records: list[dict] = []
    sink = logger.add(lambda m: records.append(m.record), level="INFO")
    yield records
    logger.remove(sink)


def chat_messages(records: list[dict]) -> list[str]:
    return [r["message"] for r in records if r["message"].startswith("google chat message")]


@pytest.mark.parametrize(
    ("name", "space", "text"),
    [(SPACE, "spaces/AAAAAAAAAAA", "'hi'"), (DM, "spaces/BBBBBBBBBBB", "'Hello'")],
    ids=["space", "dm"],
)
async def test_handle_event_logs_space_sender_and_stripped_text(
    logs: list[dict], name: str, space: str, text: str
) -> None:
    await handle_event(ChatPayload.model_validate(load_fixture(name)["chat"]), 7)

    assert chat_messages(logs) == [
        f"google chat message space={space} sender=ann@example.com text={text}"
    ]


async def test_handle_event_logs_slash_command_not_a_message(logs: list[dict]) -> None:
    await handle_event(ChatPayload.model_validate(load_fixture(SLASH_FIXTURE)["chat"]), 7)

    assert chat_messages(logs) == []
    assert [r["message"] for r in logs] == [
        "google chat command id=1 space=spaces/1234567890 sender=john.doe@example.com text='hello'"
    ]


async def test_handle_event_ignores_event_without_a_message(logs: list[dict]) -> None:
    chat = load_fixture(SPACE)["chat"]
    del chat["messagePayload"]

    await handle_event(ChatPayload.model_validate(chat), 7)

    assert chat_messages(logs) == []


async def test_handle_event_logs_nothing_for_a_payload_with_neither_message_nor_command(
    logs: list[dict],
) -> None:
    await handle_event(ChatPayload(), 7)

    assert logs == []


def test_task_runs_handle_event_under_the_request_trace_id(logs: list[dict]) -> None:
    # sync test: the task drives its async body with asyncio.run, like the real worker
    process_chat_event(load_fixture(SPACE)["chat"], "trace1234", 7)

    [record] = [r for r in logs if r["message"].startswith("google chat message")]
    assert record["extra"] == {"trace_id": "trace1234", "job": "process_chat_event"}


def queued(redis: FakeRedis) -> list[dict]:
    return [json.loads(raw) for items in redis.lists.values() for raw in items]


async def test_mention_in_a_space_is_queued_and_a_drain_dispatched(
    fake_chat: FakeChat, redis: FakeRedis, dispatched: list[tuple]
) -> None:
    token = trace_var.set("trace-abc")
    try:
        await handle_event(ChatPayload.model_validate(load_fixture(SPACE)["chat"]), 7)
    finally:
        trace_var.reset(token)

    [item] = queued(redis)
    assert item | {"enqueued_at": 0} == {
        "kind": "message",
        "space": "spaces/AAAAAAAAAAA",
        "user": "users/1001",
        "message_name": "spaces/AAAAAAAAAAA/messages/MSG1.MSG1",
        "text": "hi",
        "display_name": "Ann Example",
        "user_id": 7,
        "clarification_id": "",
        "option": "",
        "trace_id": "trace-abc",
        "enqueued_at": 0,
    }
    assert dispatched == [(DRAIN_TASK, "spaces/AAAAAAAAAAA", "users/1001", "trace-abc")]
    assert fake_chat.sent == []  # the reply comes from the drain, not the handler


async def test_queue_item_carries_the_app_user_id_and_no_email(
    redis: FakeRedis, dispatched: list[tuple]
) -> None:
    await handle_event(ChatPayload.model_validate(load_fixture(SPACE)["chat"]), 7)

    [item] = queued(redis)
    assert item["user_id"] == 7
    assert "email" not in item


async def test_duplicate_event_is_queued_once_but_still_dispatches(
    redis: FakeRedis, dispatched: list[tuple]
) -> None:
    chat = ChatPayload.model_validate(load_fixture(SPACE)["chat"])

    await handle_event(chat, 7)
    await handle_event(chat, 7)

    assert len(queued(redis)) == 1
    # the first delivery may have died before dispatching; an idle drain is harmless
    assert len(dispatched) == 2


async def test_dm_gets_the_spaces_only_reply_and_nothing_is_queued(
    fake_chat: FakeChat, redis: FakeRedis, dispatched: list[tuple]
) -> None:
    await handle_event(ChatPayload.model_validate(load_fixture(DM)["chat"]), 7)

    assert fake_chat.sent == [("spaces/BBBBBBBBBBB", DM_REPLY)]
    assert queued(redis) == []
    assert dispatched == []


async def test_mention_without_text_gets_a_hint_and_nothing_is_queued(
    fake_chat: FakeChat, redis: FakeRedis, dispatched: list[tuple]
) -> None:
    chat = load_fixture(SPACE)["chat"]
    message = chat["messagePayload"]["message"]
    message["text"] = ""
    message["argumentText"] = "  "

    await handle_event(ChatPayload.model_validate(chat), 7)

    assert fake_chat.sent == [("spaces/AAAAAAAAAAA", EMPTY_REPLY)]
    assert queued(redis) == []
    assert dispatched == []


async def test_mention_without_sender_is_ignored(
    fake_chat: FakeChat, redis: FakeRedis, dispatched: list[tuple]
) -> None:
    chat = load_fixture(SPACE)["chat"]
    del chat["messagePayload"]["message"]["sender"]

    await handle_event(ChatPayload.model_validate(chat), 7)

    assert fake_chat.sent == []
    assert queued(redis) == []
    assert dispatched == []


async def test_reset_command_is_queued_and_a_drain_dispatched(
    monkeypatch: pytest.MonkeyPatch, redis: FakeRedis, dispatched: list[tuple]
) -> None:
    monkeypatch.setattr(google_chat.settings, "google_chat_reset_command_id", 1)

    await handle_event(ChatPayload.model_validate(load_fixture(SLASH_FIXTURE)["chat"]), 7)

    [item] = queued(redis)
    assert (item["kind"], item["space"], item["user"]) == (
        "reset",
        "spaces/1234567890",
        "users/1234567890",
    )
    assert len(dispatched) == 1
    assert dispatched[0][:3] == (DRAIN_TASK, "spaces/1234567890", "users/1234567890")


@pytest.mark.parametrize("reset_id", [0, 2], ids=["not-configured", "other-id"])
async def test_other_command_ids_are_only_logged(
    monkeypatch: pytest.MonkeyPatch,
    redis: FakeRedis,
    dispatched: list[tuple],
    reset_id: int,
) -> None:
    # the fixture's command id is 1; with 0 nothing is a reset, with 2 only id 2 is
    monkeypatch.setattr(google_chat.settings, "google_chat_reset_command_id", reset_id)

    await handle_event(ChatPayload.model_validate(load_fixture(SLASH_FIXTURE)["chat"]), 7)

    assert queued(redis) == []
    assert dispatched == []


def test_task_passes_its_trace_id_on_to_the_drain(dispatched: list[tuple]) -> None:
    process_chat_event(load_fixture(SPACE)["chat"], "trace1234", 7)

    assert dispatched == [(DRAIN_TASK, "spaces/AAAAAAAAAAA", "users/1001", "trace1234")]


def click_chat(**overrides: str) -> ChatPayload:
    chat = click_event("token")["chat"]
    chat["actionParameters"] = {
        "clarification_id": "abc",
        "option": "1",
        "label": "Shipping",
        "asker": "users/1001",
        **overrides,
    }
    return ChatPayload.model_validate(chat)


async def test_click_is_queued_as_a_choice_on_the_clickers_conversation(
    redis: FakeRedis, dispatched: list[tuple]
) -> None:
    trace_var.set("trace-abc")

    await handle_event(click_chat(), 7)

    [raw] = redis.lists["chat:q:spaces/AAAAAAAAAAA:users/1001"]
    item = conversation_queue.QueueItem.model_validate_json(raw)
    assert (item.kind, item.clarification_id, item.option, item.text) == (
        "choice",
        "abc",
        "1",
        "Shipping",
    )
    assert (item.user, item.user_id) == ("users/1001", 7)
    assert item.message_name == "spaces/AAAAAAAAAAA/messages/CARD1.CARD1#click"
    assert dispatched == [(DRAIN_TASK, "spaces/AAAAAAAAAAA", "users/1001", "trace-abc")]


async def test_a_second_click_on_the_same_card_is_queued_once(redis: FakeRedis) -> None:
    await handle_event(click_chat(), 7)
    await handle_event(click_chat(option="0"), 7)

    assert len(redis.lists["chat:q:spaces/AAAAAAAAAAA:users/1001"]) == 1


async def test_click_without_a_clarification_id_is_ignored(
    redis: FakeRedis, dispatched: list[tuple]
) -> None:
    chat = click_chat()
    del chat.action_parameters["clarification_id"]

    await handle_event(chat, 7)

    assert redis.lists == {}
    assert dispatched == []
