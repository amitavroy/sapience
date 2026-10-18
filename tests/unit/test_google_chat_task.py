import pytest

from app.core.logger import logger
from app.schemas.google_chat import ChatPayload
from app.services.google_chat import handle_event
from app.tasks.google_chat import process_chat_event
from tests.google_chat_helpers import CHAT_FIXTURES, load_fixture

SPACE, DM = CHAT_FIXTURES


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
