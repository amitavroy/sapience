import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agent import graph as graph_module
from app.agent import models
from app.agent.graph import MAX_REPLY_CHARS, TRUNCATED_SUFFIX, build_graph, finalize
from app.agent.models import ConversationError, get_model
from app.agent.state import ConversationContext
from app.core.config import settings
from app.services.conversation import run_turn, thread_id
from tests.agent_helpers import FakeChatModel

ANN = ConversationContext(space="spaces/A", user="users/1", display_name="Ann")


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> FakeChatModel:
    fake = FakeChatModel(replies=["Hi Ana", "Your name is Ana"])
    monkeypatch.setattr(graph_module, "get_model", lambda role: fake)
    return fake


@pytest.fixture
def graph(model: FakeChatModel):
    return build_graph(InMemorySaver())


def texts(call: list) -> list[str]:
    return [m.text for m in call]


def test_thread_id_is_per_space_and_user() -> None:
    assert thread_id("spaces/A", "users/1") == "gchat:spaces/A:users/1"
    assert thread_id("spaces/A", "users/1") != thread_id("spaces/A", "users/2")
    assert thread_id("spaces/A", "users/1") != thread_id("spaces/B", "users/1")


async def test_second_turn_sees_the_first_turn(graph, model: FakeChatModel) -> None:
    first = await run_turn(graph, ANN, "spaces/A/messages/1", "my name is Ana")
    second = await run_turn(graph, ANN, "spaces/A/messages/2", "what is my name?")

    assert (first, second) == ("Hi Ana", "Your name is Ana")
    seen = texts(model.calls[1])
    assert "my name is Ana" in seen
    assert "Hi Ana" in seen
    assert seen[-1] == "what is my name?"


@pytest.mark.parametrize(
    "other",
    [
        ConversationContext(space="spaces/A", user="users/2", display_name="Bob"),
        ConversationContext(space="spaces/B", user="users/1", display_name="Ann"),
    ],
    ids=["other-user", "other-space"],
)
async def test_other_user_or_space_starts_fresh(
    graph, model: FakeChatModel, other: ConversationContext
) -> None:
    await run_turn(graph, ANN, "spaces/A/messages/1", "my name is Ana")
    await run_turn(graph, other, "spaces/A/messages/2", "what is my name?")

    seen = texts(model.calls[1])
    assert "my name is Ana" not in seen
    assert "Hi Ana" not in seen


async def test_system_prompt_greets_the_user_by_display_name(graph, model: FakeChatModel) -> None:
    await run_turn(graph, ANN, "spaces/A/messages/1", "hi")

    system = model.calls[0][0]
    assert system.type == "system"
    assert "Ann" in system.text


def test_finalize_truncates_a_long_reply() -> None:
    out = finalize({"messages": [AIMessage("x" * 9000)], "reply": ""})

    assert len(out["reply"]) == MAX_REPLY_CHARS
    assert out["reply"].endswith(TRUNCATED_SUFFIX)


def test_finalize_keeps_a_short_reply() -> None:
    assert finalize({"messages": [AIMessage("hello")], "reply": ""}) == {"reply": "hello"}


@pytest.mark.parametrize(("key", "chat_model"), [("", "m"), ("k", "")])
def test_get_model_without_key_or_model_raises(
    monkeypatch: pytest.MonkeyPatch, key: str, chat_model: str
) -> None:
    monkeypatch.setattr(settings, "llm_api_key", key)
    monkeypatch.setattr(settings, "llm_chat_model", chat_model)
    models.get_model.cache_clear()

    with pytest.raises(ConversationError):
        get_model("chat")
