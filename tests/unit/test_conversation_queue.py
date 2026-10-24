from contextlib import asynccontextmanager

import httpx
import openai
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatResult
from langgraph.checkpoint.memory import InMemorySaver

from app.agent import graph as graph_module
from app.agent.graph import build_graph
from app.agent.state import ConversationContext
from app.core.google_chat_client import GoogleChatError
from app.services import conversation, conversation_queue
from app.services.conversation_queue import QueueItem, drain, enqueue, lock_key, queue_key
from app.services.google_chat import FAILURE_REPLY
from tests.agent_helpers import FakeChat, FakeChatModel, FakeRedis

SPACE, USER = "spaces/A", "users/1"
CTX = ConversationContext(space=SPACE, user=USER, display_name="Ann")


def item(n: int, **kwargs) -> QueueItem:
    return QueueItem(
        space=SPACE, user=USER, message_name=f"{SPACE}/messages/{n}", text=f"m{n}", **kwargs
    )


@pytest.fixture
def redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def slept(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    delays: list[float] = []

    async def sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(conversation.asyncio, "sleep", sleep)
    return delays


class FlakyModel(FakeChatModel):
    """Raises `error` on its first `failures` calls, then answers like FakeChatModel."""

    failures: int = 0
    error: Exception = openai.APIConnectionError(request=httpx.Request("POST", "http://llm"))
    attempts: int = 0

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.attempts += 1
        if self.attempts <= self.failures:
            raise self.error
        return super()._generate(messages, stop, run_manager, **kwargs)


@pytest.fixture
def use_model(monkeypatch: pytest.MonkeyPatch):
    """Runs process_item against the real graph on an in-memory checkpointer."""
    saver = InMemorySaver()

    def install(model: FakeChatModel):
        monkeypatch.setattr(graph_module, "get_model", lambda role: model)

        @asynccontextmanager
        async def open_graph():
            yield build_graph(saver)

        monkeypatch.setattr(conversation, "open_graph", open_graph)
        return build_graph(saver)

    return install


async def checkpointed(graph) -> list[tuple[str, str]]:
    state = await graph.aget_state(conversation._config(CTX))
    return [(type(m).__name__, m.text) for m in state.values["messages"]]


# queue and lock


async def test_items_are_processed_in_order(redis: FakeRedis) -> None:
    for n in (1, 2, 3):
        await enqueue(redis, item(n))
    seen: list[str] = []

    async def process(it: QueueItem) -> None:
        seen.append(it.text)

    await drain(redis, SPACE, USER, process)

    assert seen == ["m1", "m2", "m3"]
    assert redis.lists[queue_key(SPACE, USER)] == []
    assert lock_key(SPACE, USER) not in redis.values


async def test_second_drain_exits_while_the_lock_is_held(redis: FakeRedis) -> None:
    await enqueue(redis, item(1))
    redis.values[lock_key(SPACE, USER)] = "someone-else"
    seen: list[str] = []

    async def process(it: QueueItem) -> None:
        seen.append(it.text)

    await drain(redis, SPACE, USER, process)

    assert seen == []
    assert len(redis.lists[queue_key(SPACE, USER)]) == 1
    assert redis.values[lock_key(SPACE, USER)] == "someone-else"


async def test_item_pushed_before_the_lock_is_released_is_not_stranded(
    redis: FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    await enqueue(redis, item(1))
    seen: list[str] = []
    real_release = conversation_queue.release
    pushed = False

    async def release_after_a_late_push(r, key, token) -> None:
        nonlocal pushed
        if not pushed:  # lands after the last pop, before the lock goes
            pushed = True
            await enqueue(r, item(2))
        await real_release(r, key, token)

    async def process(it: QueueItem) -> None:
        seen.append(it.text)

    monkeypatch.setattr(conversation_queue, "release", release_after_a_late_push)

    await drain(redis, SPACE, USER, process)

    assert seen == ["m1", "m2"]


async def test_same_message_name_is_queued_once(redis: FakeRedis) -> None:
    assert await enqueue(redis, item(1)) is True
    assert await enqueue(redis, item(1)) is False

    assert len(redis.lists[queue_key(SPACE, USER)]) == 1


async def test_release_never_deletes_another_workers_lock(redis: FakeRedis) -> None:
    redis.values[lock_key(SPACE, USER)] = "theirs"

    await conversation_queue.release(redis, lock_key(SPACE, USER), "mine")

    assert redis.values[lock_key(SPACE, USER)] == "theirs"


# retries, failure and expiry


async def test_retryable_error_then_success_leaves_one_turn_in_history(
    use_model, slept: list[float]
) -> None:
    graph = use_model(FlakyModel(replies=["fine"], failures=2))
    chat = FakeChat()

    await conversation.process_item(chat, item(1))

    assert chat.sent == [(SPACE, "fine")]
    assert slept == [5, 15]
    assert await checkpointed(graph) == [("HumanMessage", "m1"), ("AIMessage", "fine")]


async def test_final_failure_posts_the_apology_and_the_next_item_runs_clean(
    use_model, slept: list[float]
) -> None:
    model = FlakyModel(replies=["second answer"], failures=4)  # first try + three retries
    graph = use_model(model)
    chat = FakeChat()

    await conversation.process_item(chat, item(1))

    assert slept == [5, 15, 60]
    assert chat.sent == [(SPACE, FAILURE_REPLY)]
    assert await checkpointed(graph) == [("HumanMessage", "m1"), ("AIMessage", FAILURE_REPLY)]

    await conversation.process_item(chat, item(2))

    assert chat.sent[-1] == (SPACE, "second answer")
    seen = [m.text for m in model.calls[-1] if isinstance(m, HumanMessage | AIMessage)]
    assert seen == ["m1", FAILURE_REPLY, "m2"]


async def test_failure_does_not_stop_the_drain(
    redis: FakeRedis, use_model, slept: list[float]
) -> None:
    graph = use_model(FlakyModel(replies=["ok"], failures=4))
    chat = FakeChat()
    for n in (1, 2):
        await enqueue(redis, item(n))

    async def process(it: QueueItem) -> None:
        await conversation.process_item(chat, it)

    await drain(redis, SPACE, USER, process)

    assert chat.sent == [(SPACE, FAILURE_REPLY), (SPACE, "ok")]
    assert redis.lists[queue_key(SPACE, USER)] == []
    assert [t for _, t in await checkpointed(graph)][-1] == "ok"


async def test_non_retryable_error_is_not_retried(use_model, slept: list[float]) -> None:
    model = FlakyModel(failures=5, error=ValueError("bad request"))
    use_model(model)
    chat = FakeChat()

    await conversation.process_item(chat, item(1))

    assert model.attempts == 1
    assert slept == []
    assert chat.sent == [(SPACE, FAILURE_REPLY)]


async def test_expired_item_gets_the_apology_without_a_model_call(
    use_model, slept: list[float]
) -> None:
    model = FakeChatModel()
    use_model(model)
    chat = FakeChat()
    stale = item(1, enqueued_at=conversation.time.time() - conversation.MESSAGE_TTL - 1)

    await conversation.process_item(chat, stale)

    assert model.calls == []
    assert chat.sent == [(SPACE, FAILURE_REPLY)]


@pytest.mark.parametrize(
    ("error", "retryable"),
    [
        (
            openai.RateLimitError(
                "slow down",
                response=httpx.Response(429, request=httpx.Request("POST", "http://llm")),
                body=None,
            ),
            True,
        ),
        (GoogleChatError("chat down", status=503), True),
        (GoogleChatError("forbidden", status=403), False),
        (ValueError("nope"), False),
    ],
    ids=["rate-limit", "chat-5xx", "chat-4xx", "other"],
)
def test_is_retryable(error: Exception, retryable: bool) -> None:
    assert conversation.is_retryable(error) is retryable
