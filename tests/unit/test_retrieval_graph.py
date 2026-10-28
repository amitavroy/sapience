from contextlib import asynccontextmanager

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agent import graph as graph_module
from app.agent.graph import build_graph
from app.agent.nodes.retrieval import Grade, NeedsKb, Option, Rewrite, validate_grade
from app.agent.state import ConversationContext
from app.agent.tools.knowledge import NO_KNOWLEDGE, NOTHING_FOUND
from app.services import conversation
from app.services.conversation import StaleChoiceError, TurnResult, run_turn, thread_id
from app.services.conversation_queue import QueueItem
from app.services.google_chat import FAILURE_REPLY
from tests.agent_helpers import FakeChat, FakeChatModel, FakeSearch, NullLog, make_chunk

QUESTION = "how do refunds work?"
CHUNKS = [make_chunk(1, "Refunds take 5 days"), make_chunk(2, "Shipping takes 2 days")]


def ctx_with(search: FakeSearch | None, user_id: int | None = 5) -> ConversationContext:
    return ConversationContext(
        space="spaces/A", user="users/1", display_name="Ann", user_id=user_id, search=search
    )


@pytest.fixture
def chat_model() -> FakeChatModel:
    return FakeChatModel(
        replies=["the answer"],
        structured={
            "Rewrite": Rewrite(queries=["refund policy", "returns"]),
            "Grade": Grade(verdict="clear", relevant_doc_ids=[1]),
        },
    )


@pytest.fixture
def classify_model() -> FakeChatModel:
    return FakeChatModel(structured={"NeedsKb": NeedsKb(needs_kb=True)})


@pytest.fixture
def graph(monkeypatch: pytest.MonkeyPatch, chat_model, classify_model):
    models = {"chat": chat_model, "summary": chat_model, "classify": classify_model}
    monkeypatch.setattr(graph_module, "get_model", lambda role: models[role])
    return build_graph(InMemorySaver())


def system_text(model: FakeChatModel, call: int = 0) -> str:
    return model.calls[call][0].text


def structured_names(model: FakeChatModel) -> list[str]:
    return [name for name, _ in model.structured_calls]


async def ask_turn(graph, ctx, text: str = QUESTION, n: int = 1) -> TurnResult:
    return await run_turn(graph, ctx, f"spaces/A/messages/{n}", text)


async def ask(graph, ctx, text: str = QUESTION, n: int = 1) -> str | None:
    return (await ask_turn(graph, ctx, text, n)).reply


async def test_small_talk_skips_retrieval(graph, chat_model, classify_model) -> None:
    classify_model.structured["NeedsKb"] = NeedsKb(needs_kb=False)
    search = FakeSearch(probe=CHUNKS)

    reply = await ask(graph, ctx_with(search), "thanks!")

    assert reply == "the answer"
    assert structured_names(classify_model) == ["NeedsKb"]
    assert structured_names(chat_model) == []
    assert search.calls == []
    assert "knowledge base follow" not in system_text(chat_model)


@pytest.mark.parametrize(
    "ctx",
    [ctx_with(None), ctx_with(FakeSearch(), user_id=None)],
    ids=["no-search", "no-user"],
)
async def test_without_a_search_or_user_nothing_is_classified(
    graph, chat_model, classify_model, ctx: ConversationContext
) -> None:
    assert await ask(graph, ctx) == "the answer"

    assert classify_model.structured_calls == []
    assert chat_model.structured_calls == []


async def test_empty_probe_is_no_match_without_a_grade_call(graph, chat_model) -> None:
    search = FakeSearch(probe=[])

    await ask(graph, ctx_with(search))

    assert structured_names(chat_model) == ["Rewrite"]
    assert [c[0] for c in search.calls] == ["probe"]
    prompt = system_text(chat_model)
    assert "found nothing relevant" in prompt
    assert "Do not answer from memory" in prompt
    assert "Sources:" not in prompt


async def test_clear_probes_once_then_searches_the_graded_documents(graph, chat_model) -> None:
    search = FakeSearch(probe=CHUNKS, deep=[CHUNKS[0]])

    reply = await ask(graph, ctx_with(search))

    assert reply == "the answer"
    # one probe carrying every rewritten query, one deep search on the graded doc ids
    assert search.calls == [
        ("probe", 5, ["refund policy", "returns"]),
        ("deep", 5, "refund policy", [1]),
    ]
    prompt = system_text(chat_model)
    assert "Refunds take 5 days" in prompt
    assert "https://example.com/1" in prompt
    assert "Shipping takes 2 days" not in prompt
    # grounded answers that cite the documents they used
    assert "Sources:" in prompt
    assert "only from them" in prompt


async def test_grade_sees_the_probe_chunks_with_ids(graph, chat_model) -> None:
    await ask(graph, ctx_with(FakeSearch(probe=CHUNKS, deep=[CHUNKS[0]])))

    [grade_input] = [m for n, m in chat_model.structured_calls if n == "Grade"]
    text = grade_input[-1].text
    assert QUESTION in text
    assert "doc 1" in text and "doc 2" in text


async def test_unknown_doc_ids_from_the_grade_are_dropped(graph, chat_model) -> None:
    chat_model.structured["Grade"] = Grade(verdict="clear", relevant_doc_ids=[1, 99])
    search = FakeSearch(probe=CHUNKS, deep=[CHUNKS[0]])

    await ask(graph, ctx_with(search))

    assert search.calls[-1] == ("deep", 5, "refund policy", [1])


async def test_clear_with_only_unknown_ids_becomes_no_match(graph, chat_model) -> None:
    chat_model.structured["Grade"] = Grade(verdict="clear", relevant_doc_ids=[99])
    search = FakeSearch(probe=CHUNKS)

    await ask(graph, ctx_with(search))

    assert [c[0] for c in search.calls] == ["probe"]
    assert "found nothing relevant" in system_text(chat_model)


async def test_no_match_verdict_tells_the_agent_nothing_was_found(graph, chat_model) -> None:
    chat_model.structured["Grade"] = Grade(verdict="no_match")
    search = FakeSearch(probe=CHUNKS)

    await ask(graph, ctx_with(search))

    assert [c[0] for c in search.calls] == ["probe"]
    assert "found nothing relevant" in system_text(chat_model)


async def test_empty_deep_search_is_no_match(graph, chat_model) -> None:
    search = FakeSearch(probe=CHUNKS, deep=[])

    await ask(graph, ctx_with(search))

    assert "found nothing relevant" in system_text(chat_model)


async def test_ambiguous_pauses_with_a_card_and_no_reply(graph, chat_model) -> None:
    chat_model.structured["Grade"] = Grade(
        verdict="ambiguous",
        options=[Option(label="Refunds", doc_ids=[1]), Option(label="Shipping", doc_ids=[2])],
    )
    search = FakeSearch(probe=CHUNKS, deep=CHUNKS)

    result = await ask_turn(graph, ctx_with(search))

    assert result.reply is None
    assert result.card.labels == ["Refunds", "Shipping"]
    assert result.card.asker == "users/1"
    assert [c[0] for c in search.calls] == ["probe"]  # no deep search until the user answers


@pytest.fixture
def paused(chat_model):
    """An ambiguous question asked on a fresh thread: (search, card)."""
    chat_model.structured["Grade"] = Grade(
        verdict="ambiguous",
        options=[Option(label="Refunds", doc_ids=[1]), Option(label="Shipping", doc_ids=[2])],
    )
    return FakeSearch(probe=CHUNKS, deep=[CHUNKS[1]])


def click(card, option: str) -> dict:
    return {"clarification_id": card.clarification_id, "option": option}


async def test_click_searches_only_that_option_and_answers(graph, chat_model, paused) -> None:
    ctx = ctx_with(paused)
    card = (await ask_turn(graph, ctx)).card

    result = await run_turn(graph, ctx, "spaces/A/messages/card#click", "", choice=click(card, "1"))

    assert result.reply == "the answer"
    assert paused.calls[-1] == ("deep", 5, f"{QUESTION} — Shipping", [2])
    assert "Shipping takes 2 days" in system_text(chat_model)
    assert not (
        await graph.aget_state({"configurable": {"thread_id": thread_id(ctx.space, ctx.user)}})
    ).interrupts


async def test_none_of_these_ends_the_pause_with_an_invitation(graph, paused) -> None:
    ctx = ctx_with(paused)
    card = (await ask_turn(graph, ctx)).card

    result = await run_turn(
        graph, ctx, "spaces/A/messages/card#click", "", choice=click(card, "none")
    )

    assert result.reply == "No problem. Tell me what you're looking for."
    assert [c[0] for c in paused.calls] == ["probe"]


async def test_a_stale_click_is_refused_without_touching_the_thread(
    graph, chat_model, paused
) -> None:
    ctx = ctx_with(paused)
    card = (await ask_turn(graph, ctx)).card
    calls = len(chat_model.calls)

    with pytest.raises(StaleChoiceError):
        await run_turn(graph, ctx, "m#click", "", choice={"clarification_id": "old", "option": "0"})

    assert len(chat_model.calls) == calls
    # the pause is still there for the right click
    result = await run_turn(graph, ctx, "m#click", "", choice=click(card, "0"))
    assert result.reply == "the answer"


async def test_a_click_on_a_thread_that_is_not_paused_is_refused(graph, chat_model) -> None:
    with pytest.raises(StaleChoiceError):
        await run_turn(
            graph,
            ctx_with(FakeSearch()),
            "m#click",
            "",
            choice={"clarification_id": "x", "option": "0"},
        )

    assert chat_model.calls == []


async def test_a_typed_reply_while_paused_is_answered_as_a_new_question(
    graph, chat_model, classify_model, paused
) -> None:
    ctx = ctx_with(paused)
    await ask_turn(graph, ctx)
    chat_model.structured["Grade"] = Grade(verdict="clear", relevant_doc_ids=[1])

    result = await ask_turn(graph, ctx, "what about gift cards?", n=2)

    assert result.reply == "the answer"
    assert structured_names(classify_model) == ["NeedsKb", "NeedsKb"]  # asked again as new


async def test_rewrite_is_capped_and_falls_back_to_the_question(graph, chat_model) -> None:
    chat_model.structured["Rewrite"] = Rewrite(queries=["a", " ", "b", "c", "d"])
    search = FakeSearch(probe=[])
    await ask(graph, ctx_with(search))
    assert search.calls[0] == ("probe", 5, ["a", "b", "c"])

    chat_model.structured["Rewrite"] = Rewrite(queries=["", "  "])
    search = FakeSearch(probe=[])
    await ask(graph, ctx_with(search), n=2)
    assert search.calls[0] == ("probe", 5, [QUESTION])


async def test_rewrite_sees_the_earlier_messages(graph, chat_model, classify_model) -> None:
    classify_model.structured["NeedsKb"] = NeedsKb(needs_kb=False)
    await ask(graph, ctx_with(FakeSearch()), "we sell shoes")
    classify_model.structured["NeedsKb"] = NeedsKb(needs_kb=True)

    await ask(graph, ctx_with(FakeSearch()), "and returns?", n=2)

    [rewrite_input] = [m for n, m in chat_model.structured_calls if n == "Rewrite"]
    assert "we sell shoes" in rewrite_input[-1].text


async def test_next_turn_starts_without_last_turns_chunks(
    graph, chat_model, classify_model
) -> None:
    search = FakeSearch(probe=CHUNKS, deep=[CHUNKS[0]])
    await ask(graph, ctx_with(search))
    assert "Refunds take 5 days" in system_text(chat_model, 0)

    classify_model.structured["NeedsKb"] = NeedsKb(needs_kb=False)
    await ask(graph, ctx_with(search), "thanks", n=2)

    assert "Refunds take 5 days" not in system_text(chat_model, 1)


def _search_call(query: str) -> AIMessage:
    return AIMessage(
        "", tool_calls=[{"name": "search_knowledge", "args": {"query": query}, "id": "call-1"}]
    )


async def test_search_tool_uses_the_user_id_from_context(graph, chat_model, classify_model) -> None:
    classify_model.structured["NeedsKb"] = NeedsKb(needs_kb=False)
    chat_model.replies = [_search_call("onboarding"), "done"]
    search = FakeSearch(deep=[make_chunk(3, "Day one: laptop")])

    await ask(graph, ctx_with(search, user_id=42), "and onboarding?")

    assert search.calls == [("deep", 42, "onboarding", None)]
    result = chat_model.calls[1][-1]
    assert result.type == "tool"
    assert "Day one: laptop" in result.text


async def test_search_tool_reports_an_empty_result(graph, chat_model, classify_model) -> None:
    classify_model.structured["NeedsKb"] = NeedsKb(needs_kb=False)
    chat_model.replies = [_search_call("x"), "done"]

    await ask(graph, ctx_with(FakeSearch(deep=[])))

    assert chat_model.calls[1][-1].text == NOTHING_FOUND


async def test_search_tool_without_a_search_says_nothing_is_connected(graph, chat_model) -> None:
    chat_model.replies = [_search_call("x"), "done"]

    await ask(graph, ctx_with(None))

    assert chat_model.calls[1][-1].text == NO_KNOWLEDGE


@pytest.mark.parametrize("failing", ["probe", "deep", "grade", "classify"])
async def test_a_failure_in_retrieval_ends_in_the_apology(
    monkeypatch: pytest.MonkeyPatch, graph, chat_model, classify_model, failing: str
) -> None:
    error = RuntimeError("embedder down")
    search = FakeSearch(probe=CHUNKS, deep=[CHUNKS[0]])
    if failing in ("probe", "deep"):

        async def boom(*args, **kwargs):
            raise error

        monkeypatch.setattr(search, "probe" if failing == "probe" else "deep_search", boom)
    elif failing == "grade":
        chat_model.structured["Grade"] = error
    else:
        classify_model.structured["NeedsKb"] = error

    @asynccontextmanager
    async def open_graph():
        yield graph

    monkeypatch.setattr(conversation, "open_graph", open_graph)
    chat = FakeChat()
    item = QueueItem(
        space="spaces/A",
        user="users/1",
        message_name="spaces/A/messages/1",
        text=QUESTION,
        display_name="Ann",
        user_id=5,
    )

    await conversation.process_item(chat, NullLog(), item, search)

    assert chat.sent == [("spaces/A", FAILURE_REPLY)]


def _probe() -> list:
    return [make_chunk(1), make_chunk(2), make_chunk(3)]


def test_validate_grade_ambiguous_with_two_options_asks_with_their_valid_documents() -> None:
    grade = Grade(
        verdict="ambiguous",
        options=[Option(label="A", doc_ids=[1]), Option(label="B", doc_ids=[2, 99])],
    )

    verdict, doc_ids, options = validate_grade(grade, _probe())

    assert (verdict, doc_ids) == ("ambiguous", [])
    assert [(o.label, o.doc_ids) for o in options] == [("A", [1]), ("B", [2])]


def test_validate_grade_ambiguous_with_one_valid_option_is_clear_on_its_documents() -> None:
    grade = Grade(
        verdict="ambiguous",
        options=[Option(label="A", doc_ids=[2, 99]), Option(label="B", doc_ids=[98])],
    )

    assert validate_grade(grade, _probe()) == ("clear", [2], [])


def test_validate_grade_ambiguous_with_no_valid_options_is_no_match() -> None:
    grade = Grade(verdict="ambiguous", options=[Option(label="A", doc_ids=[98])])

    assert validate_grade(grade, _probe()) == ("no_match", [], [])


def test_validate_grade_clear_drops_unknown_and_repeated_ids() -> None:
    grade = Grade(verdict="clear", relevant_doc_ids=[3, 99, 3, 1])

    assert validate_grade(grade, _probe()) == ("clear", [3, 1], [])
