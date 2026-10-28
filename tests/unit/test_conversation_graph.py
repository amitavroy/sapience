import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agent import graph as graph_module
from app.agent.graph import MAX_REPLY_CHARS, TRUNCATED_SUFFIX, build_graph, finalize
from app.agent.models import ConversationError, get_model
from app.agent.state import ConversationContext
from app.agent.tools.knowledge import NO_KNOWLEDGE, search_knowledge
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

    assert (first.reply, second.reply) == ("Hi Ana", "Your name is Ana")
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

    with pytest.raises(ConversationError):
        get_model("chat")


@pytest.mark.parametrize(
    ("role", "summary", "classify", "expected"),
    [
        ("chat", "s", "c", "m"),
        ("summary", "s", "", "s"),
        ("summary", "", "", "m"),
        ("classify", "", "c", "c"),
        ("classify", "", "", "m"),
    ],
)
def test_get_model_picks_the_role_model_or_falls_back_to_chat(
    monkeypatch: pytest.MonkeyPatch, role: str, summary: str, classify: str, expected: str
) -> None:
    monkeypatch.setattr(settings, "llm_api_key", "k")
    monkeypatch.setattr(settings, "llm_chat_model", "m")
    monkeypatch.setattr(settings, "llm_summary_model", summary)
    monkeypatch.setattr(settings, "llm_classify_model", classify)

    assert get_model(role).model_name == expected


def test_each_model_gets_its_own_http_client(monkeypatch: pytest.MonkeyPatch) -> None:
    # a shared client stays bound to the first task's event loop ("Event loop is closed")
    monkeypatch.setattr(settings, "llm_api_key", "k")
    monkeypatch.setattr(settings, "llm_chat_model", "m")

    first, second = get_model("chat"), get_model("chat")

    assert first is not second
    assert first.root_async_client._client is not second.root_async_client._client


def _search_call(query: str) -> AIMessage:
    return AIMessage(
        "", tool_calls=[{"name": "search_knowledge", "args": {"query": query}, "id": "call-1"}]
    )


async def test_tool_call_runs_with_the_space_from_context(
    monkeypatch: pytest.MonkeyPatch, model: FakeChatModel, graph
) -> None:
    model.replies = [_search_call("onboarding"), "Nothing connected yet"]
    seen: list[tuple[str, str]] = []
    original = search_knowledge.coroutine

    async def spy(query, runtime):
        seen.append((query, runtime.context.space))
        return await original(query, runtime)

    monkeypatch.setattr(search_knowledge, "coroutine", spy)

    reply = await run_turn(graph, ANN, "spaces/A/messages/1", "what is our onboarding?")

    assert reply.reply == "Nothing connected yet"
    assert seen == [("onboarding", "spaces/A")]
    result = model.calls[1][-1]  # the tool output is what the model sees next
    assert (result.type, result.text) == ("tool", NO_KNOWLEDGE)


def test_search_knowledge_exposes_only_the_query_to_the_model() -> None:
    assert set(search_knowledge.tool_call_schema.model_json_schema()["properties"]) == {"query"}


@pytest.fixture
def summary_model(monkeypatch: pytest.MonkeyPatch, model: FakeChatModel) -> FakeChatModel:
    """Separate fake for the "summary" role, so its calls can be told apart from the chat's."""
    summarizer = FakeChatModel(replies=["SUMMARY of the earlier talk"])
    monkeypatch.setattr(
        graph_module, "get_model", lambda role: summarizer if role == "summary" else model
    )
    return summarizer


async def _talk(graph, count: int, text: str) -> None:
    for i in range(count):
        await run_turn(graph, ANN, f"spaces/A/messages/{i}", text)


async def _stored_messages(graph) -> list:
    config = {"configurable": {"thread_id": thread_id(ANN.space, ANN.user)}}
    return (await graph.aget_state(config)).values["messages"]


async def test_history_under_the_trigger_is_not_summarized(
    summary_model: FakeChatModel, model: FakeChatModel
) -> None:
    graph = build_graph(InMemorySaver())

    await _talk(graph, 3, "short question")

    assert summary_model.calls == []
    assert len(await _stored_messages(graph)) == 6  # 3 human + 3 AI, nothing replaced


async def test_history_over_the_trigger_is_summarized_for_the_model(
    monkeypatch: pytest.MonkeyPatch, summary_model: FakeChatModel, model: FakeChatModel
) -> None:
    monkeypatch.setattr(graph_module, "SUMMARY_TRIGGER_TOKENS", 200)
    monkeypatch.setattr(graph_module, "SUMMARY_KEEP_MESSAGES", 4)
    graph = build_graph(InMemorySaver())

    await _talk(graph, 6, "a fairly long question " * 20)

    assert len(summary_model.calls) >= 1
    # summary + the last 4 messages + this turn's question, not the whole history
    last_prompt = texts(model.calls[-1])
    assert any("SUMMARY of the earlier talk" in t for t in last_prompt)
    assert len(last_prompt) < 12


async def test_summary_replaces_old_messages_in_the_checkpoint(
    monkeypatch: pytest.MonkeyPatch, summary_model: FakeChatModel, model: FakeChatModel
) -> None:
    monkeypatch.setattr(graph_module, "SUMMARY_TRIGGER_TOKENS", 200)
    monkeypatch.setattr(graph_module, "SUMMARY_KEEP_MESSAGES", 4)
    graph = build_graph(InMemorySaver())

    await _talk(graph, 6, "a fairly long question " * 20)

    stored = await _stored_messages(graph)
    assert "SUMMARY of the earlier talk" in stored[0].text
    assert len(stored) <= 4 + 2
