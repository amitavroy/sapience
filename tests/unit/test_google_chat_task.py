from contextlib import asynccontextmanager

import pytest

from app.core.logger import logger
from app.schemas.google_chat import ChatPayload
from app.services import conversation, google_chat
from app.services.google_chat import DM_REPLY, EMPTY_REPLY, FAILURE_REPLY, handle_event
from app.tasks.google_chat import process_chat_event
from tests.google_chat_helpers import CHAT_FIXTURES, SLASH_FIXTURE, load_fixture

SPACE, DM = CHAT_FIXTURES


class FakeChat:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def create_message(self, space: str, text: str) -> str:
        self.sent.append((space, text))
        return f"{space}/messages/1"


@pytest.fixture
def turns() -> list[tuple]:
    """(ctx, message_name, text) for every turn the fake graph ran."""
    return []


@pytest.fixture(autouse=True)
def fake_chat(monkeypatch: pytest.MonkeyPatch, turns: list[tuple]) -> FakeChat:
    """No test reaches Google or an LLM: the Chat client and the graph are fakes."""
    fake = FakeChat()

    @asynccontextmanager
    async def open_chat_client():
        yield fake

    @asynccontextmanager
    async def open_graph():
        yield None

    async def run_turn(graph, ctx, message_name, text) -> str:
        turns.append((ctx, message_name, text))
        return "reply"

    monkeypatch.setattr(google_chat, "_open_chat_client", open_chat_client)
    monkeypatch.setattr(conversation, "open_graph", open_graph)
    monkeypatch.setattr(conversation, "run_turn", run_turn)
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
    await handle_event(ChatPayload.model_validate(load_fixture(name)["chat"]))

    assert chat_messages(logs) == [
        f"google chat message space={space} sender=ann@example.com text={text}"
    ]


async def test_handle_event_logs_slash_command_not_a_message(logs: list[dict]) -> None:
    await handle_event(ChatPayload.model_validate(load_fixture(SLASH_FIXTURE)["chat"]))

    assert chat_messages(logs) == []
    assert [r["message"] for r in logs] == [
        "google chat command id=1 space=spaces/1234567890 sender=john.doe@example.com text='hello'"
    ]


async def test_handle_event_ignores_event_without_a_message(logs: list[dict]) -> None:
    chat = load_fixture(SPACE)["chat"]
    del chat["messagePayload"]

    await handle_event(ChatPayload.model_validate(chat))

    assert chat_messages(logs) == []


async def test_handle_event_logs_nothing_for_a_payload_with_neither_message_nor_command(
    logs: list[dict],
) -> None:
    await handle_event(ChatPayload())

    assert logs == []


def test_task_runs_handle_event_under_the_request_trace_id(logs: list[dict]) -> None:
    # sync test: the task drives its async body with asyncio.run, like the real worker
    process_chat_event(load_fixture(SPACE)["chat"], "trace1234")

    [record] = [r for r in logs if r["message"].startswith("google chat message")]
    assert record["extra"] == {"trace_id": "trace1234", "job": "process_chat_event"}


async def test_mention_in_a_space_runs_a_turn_and_posts_the_reply(
    fake_chat: FakeChat, turns: list[tuple]
) -> None:
    await handle_event(ChatPayload.model_validate(load_fixture(SPACE)["chat"]))

    [(ctx, message_name, text)] = turns
    assert (ctx.space, ctx.user, ctx.display_name) == (
        "spaces/AAAAAAAAAAA",
        "users/1001",
        "Ann Example",
    )
    assert message_name == "spaces/AAAAAAAAAAA/messages/MSG1.MSG1"
    assert text == "hi"
    assert fake_chat.sent == [("spaces/AAAAAAAAAAA", "reply")]


async def test_dm_gets_the_spaces_only_reply_and_no_turn(
    fake_chat: FakeChat, turns: list[tuple]
) -> None:
    await handle_event(ChatPayload.model_validate(load_fixture(DM)["chat"]))

    assert fake_chat.sent == [("spaces/BBBBBBBBBBB", DM_REPLY)]
    assert turns == []


async def test_mention_without_text_gets_a_hint_and_no_turn(
    fake_chat: FakeChat, turns: list[tuple]
) -> None:
    chat = load_fixture(SPACE)["chat"]
    message = chat["messagePayload"]["message"]
    message["text"] = ""
    message["argumentText"] = "  "

    await handle_event(ChatPayload.model_validate(chat))

    assert fake_chat.sent == [("spaces/AAAAAAAAAAA", EMPTY_REPLY)]
    assert turns == []


async def test_mention_without_sender_is_ignored(fake_chat: FakeChat, turns: list[tuple]) -> None:
    chat = load_fixture(SPACE)["chat"]
    del chat["messagePayload"]["message"]["sender"]

    await handle_event(ChatPayload.model_validate(chat))

    assert fake_chat.sent == []
    assert turns == []


async def test_failed_turn_posts_the_apology(
    monkeypatch: pytest.MonkeyPatch, fake_chat: FakeChat
) -> None:
    async def boom(graph, ctx, message_name, text) -> str:
        raise RuntimeError("model down")

    monkeypatch.setattr(conversation, "run_turn", boom)

    await handle_event(ChatPayload.model_validate(load_fixture(SPACE)["chat"]))

    assert fake_chat.sent == [("spaces/AAAAAAAAAAA", FAILURE_REPLY)]


async def test_failed_apology_is_logged_not_raised(
    monkeypatch: pytest.MonkeyPatch, fake_chat: FakeChat, logs: list[dict]
) -> None:
    async def boom(graph, ctx, message_name, text) -> str:
        raise RuntimeError("model down")

    async def chat_down(space: str, text: str) -> str:
        raise RuntimeError("chat down")

    monkeypatch.setattr(conversation, "run_turn", boom)
    monkeypatch.setattr(fake_chat, "create_message", chat_down)

    await handle_event(ChatPayload.model_validate(load_fixture(SPACE)["chat"]))

    assert any("could not post the failure reply" in r["message"] for r in logs)
