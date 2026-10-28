"""The clarifying question end to end through the drain: a real graph on an in-memory checkpointer,
fake models, search and Chat. What a user sees is what the Chat fake recorded."""

from contextlib import asynccontextmanager

import httpx
import openai
import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.agent import graph as graph_module
from app.agent.graph import build_graph
from app.agent.nodes.retrieval import Grade, NeedsKb, Option, Rewrite
from app.services import conversation
from app.services.conversation import thread_id
from app.services.conversation_queue import QueueItem
from app.services.google_chat import FAILURE_REPLY
from tests.agent_helpers import FakeChat, FakeChatModel, FakeSearch, NullLog, make_chunk

QUESTION = "how do refunds work?"
CHUNKS = [make_chunk(i, f"body {i}", f"Doc {i}") for i in (1, 2, 3, 4)]
SPACE, USER = "spaces/A", "users/1"
INVITATION = "No problem. Tell me what you're looking for."


class CardChat(FakeChat):
    def __init__(self) -> None:
        super().__init__()
        self.cards: list[tuple[str, str, list[dict]]] = []

    async def create_card_message(self, space: str, text: str, cards_v2: list[dict]) -> str:
        self.cards.append((space, text, cards_v2))
        return f"{space}/messages/card"


class FlakyDeepSearch(FakeSearch):
    """The first deep search fails the way a dropped connection does, the next ones work."""

    failures = 1

    async def deep_search(self, user_id, query, doc_ids):
        if self.failures:
            self.failures -= 1
            raise openai.APIConnectionError(request=httpx.Request("POST", "http://llm.test"))
        return await super().deep_search(user_id, query, doc_ids)


def two_options() -> Grade:
    return Grade(
        verdict="ambiguous",
        options=[Option(label="Refunds", doc_ids=[1]), Option(label="Shipping", doc_ids=[2])],
    )


@pytest.fixture
def chat_model() -> FakeChatModel:
    return FakeChatModel(
        replies=["the answer"],
        structured={"Rewrite": Rewrite(queries=["refund policy"]), "Grade": two_options()},
    )


@pytest.fixture
def classify_model() -> FakeChatModel:
    return FakeChatModel(structured={"NeedsKb": NeedsKb(needs_kb=True)})


@pytest.fixture
def graph(monkeypatch: pytest.MonkeyPatch, chat_model, classify_model):
    models = {"chat": chat_model, "summary": chat_model, "classify": classify_model}
    monkeypatch.setattr(graph_module, "get_model", lambda role: models[role])
    built = build_graph(InMemorySaver())

    @asynccontextmanager
    async def open_graph():
        yield built

    monkeypatch.setattr(conversation, "open_graph", open_graph)
    monkeypatch.setattr(conversation, "RETRY_DELAYS", (0,))  # retry at once, not after seconds
    return built


@pytest.fixture
def chat() -> CardChat:
    return CardChat()


@pytest.fixture
def search() -> FakeSearch:
    return FakeSearch(probe=CHUNKS, deep=[CHUNKS[1]])


def question(search: FakeSearch, chat: CardChat):
    return conversation.process_item(
        chat,
        NullLog(),
        QueueItem(
            space=SPACE,
            user=USER,
            message_name=f"{SPACE}/messages/1",
            text=QUESTION,
            display_name="Ann",
            user_id=5,
        ),
        search,
    )


def buttons(chat: CardChat) -> list[dict]:
    return chat.cards[-1][2][0]["card"]["sections"][0]["widgets"][1]["buttonList"]["buttons"]


def click(chat: CardChat, index: int, *, user: str = USER, **overrides) -> QueueItem:
    """The queue item the webhook makes for a click on the nth button of the last card."""
    params = {p["key"]: p["value"] for p in buttons(chat)[index]["onClick"]["action"]["parameters"]}
    item = QueueItem(
        kind="choice",
        space=SPACE,
        user=user,
        message_name=f"{SPACE}/messages/card#click",
        text=params["label"],
        display_name="Ann",
        user_id=5,
        clarification_id=params["clarification_id"],
        option=params["option"],
    )
    return item.model_copy(update=overrides)


async def thread(graph):
    return await graph.aget_state({"configurable": {"thread_id": thread_id(SPACE, USER)}})


def model_calls(chat_model: FakeChatModel, classify_model: FakeChatModel) -> int:
    return (
        len(chat_model.calls)
        + len(chat_model.structured_calls)
        + len(classify_model.structured_calls)
    )


async def test_ambiguous_question_posts_a_card_and_pauses_the_thread(
    graph, chat: CardChat, search: FakeSearch
) -> None:
    await question(search, chat)

    assert [b["text"] for b in buttons(chat)] == ["Refunds", "Shipping", "None of these"]
    assert chat.sent == []  # no text reply: the card is the reply
    assert (await thread(graph)).interrupts
    assert [c[0] for c in search.calls] == ["probe"]  # the deep search waits for the answer


async def test_card_has_at_most_three_options_plus_none(
    graph, chat_model, chat: CardChat, search: FakeSearch
) -> None:
    chat_model.structured["Grade"] = Grade(
        verdict="ambiguous",
        options=[Option(label=f"Option {i}", doc_ids=[i]) for i in (1, 2, 3, 4)],
    )

    await question(search, chat)

    assert [b["text"] for b in buttons(chat)] == [
        "Option 1",
        "Option 2",
        "Option 3",
        "None of these",
    ]


async def test_click_searches_only_that_option_and_posts_the_answer(
    graph, chat: CardChat, search: FakeSearch
) -> None:
    await question(search, chat)

    await conversation.process_item(chat, NullLog(), click(chat, 1), search)

    assert search.calls[-1] == ("deep", 5, f"{QUESTION} — Shipping", [2])
    assert chat.sent == [(SPACE, "the answer")]
    state = await thread(graph)
    assert not state.interrupts
    humans = [m.text for m in state.values["messages"] if m.type == "human"]
    assert humans == [QUESTION, "Chose: Shipping"]


async def test_none_of_these_ends_the_pause_with_the_invitation(
    graph, chat: CardChat, search: FakeSearch
) -> None:
    await question(search, chat)

    await conversation.process_item(chat, NullLog(), click(chat, 2), search)

    assert chat.sent == [(SPACE, INVITATION)]
    assert not (await thread(graph)).interrupts
    assert [c[0] for c in search.calls] == ["probe"]


async def test_second_click_on_the_same_card_is_dropped_without_a_model_call(
    graph, chat_model, classify_model, chat: CardChat, search: FakeSearch
) -> None:
    await question(search, chat)
    await conversation.process_item(chat, NullLog(), click(chat, 1), search)
    calls, sent = model_calls(chat_model, classify_model), list(chat.sent)

    await conversation.process_item(chat, NullLog(), click(chat, 0), search)

    assert model_calls(chat_model, classify_model) == calls
    assert chat.sent == sent


async def test_click_on_an_old_question_is_dropped_and_the_pause_stays(
    graph, chat_model, classify_model, chat: CardChat, search: FakeSearch
) -> None:
    await question(search, chat)
    calls = model_calls(chat_model, classify_model)

    await conversation.process_item(
        chat, NullLog(), click(chat, 0, clarification_id="an-older-question"), search
    )

    assert model_calls(chat_model, classify_model) == calls
    assert chat.sent == []
    assert (await thread(graph)).interrupts  # the real card still works
    await conversation.process_item(chat, NullLog(), click(chat, 0), search)
    assert chat.sent == [(SPACE, "the answer")]


async def test_click_by_another_user_is_dropped(
    graph, chat_model, classify_model, chat: CardChat, search: FakeSearch
) -> None:
    await question(search, chat)
    calls = model_calls(chat_model, classify_model)

    # their own thread has no pause, so nothing on it can be resumed
    await conversation.process_item(chat, NullLog(), click(chat, 0, user="users/2"), search)

    assert model_calls(chat_model, classify_model) == calls
    assert chat.sent == []
    assert (await thread(graph)).interrupts


async def test_retry_after_a_dropped_connection_resumes_from_the_paused_checkpoint(
    graph, chat: CardChat
) -> None:
    search = FlakyDeepSearch(probe=CHUNKS, deep=[CHUNKS[1]])
    await question(search, chat)

    await conversation.process_item(chat, NullLog(), click(chat, 1), search)

    assert search.failures == 0  # the first attempt really failed
    assert chat.sent == [(SPACE, "the answer")]  # one answer, no apology
    state = await thread(graph)
    assert not state.interrupts
    humans = [m.text for m in state.values["messages"] if m.type == "human"]
    assert humans == [QUESTION, "Chose: Shipping"]  # the click is in the history once


async def test_a_failed_resume_apologises_and_ends_the_pause(graph, chat: CardChat) -> None:
    search = FakeSearch(probe=CHUNKS, deep=[CHUNKS[1]], error=None)
    await question(search, chat)
    search.error = RuntimeError("search down")  # not retryable

    await conversation.process_item(chat, NullLog(), click(chat, 1), search)

    assert chat.sent == [(SPACE, FAILURE_REPLY)]
    assert not (await thread(graph)).interrupts
    # the card is now stale: a later click on it is dropped, not answered
    await conversation.process_item(chat, NullLog(), click(chat, 0), search)
    assert chat.sent == [(SPACE, FAILURE_REPLY)]
