from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Message, MessageRole, MessageStatus
from app.services import conversation, conversation_log
from app.services.conversation_log import ConversationKey
from app.services.conversation_queue import QueueItem
from app.services.google_chat import FAILURE_REPLY
from tests.agent_helpers import FakeChat, FakeGraph

ITEM = QueueItem(
    space="spaces/A",
    user="users/1",
    message_name="spaces/A/messages/1",
    text="hi",
    display_name="Ann",
)


class SessionLog:
    """A ConversationLog over the SQLite test session; `fail` names methods that raise."""

    def __init__(self, db: AsyncSession, fail: frozenset[str] = frozenset()) -> None:
        self.db = db
        self.fail = fail

    def _check(self, method: str) -> None:
        if method in self.fail:
            raise RuntimeError(f"{method} db down")

    async def record_user_message(self, key: ConversationKey, message_name: str, text: str):
        self._check("record_user_message")
        await conversation_log.record_user_message(self.db, key, message_name, text)

    async def record_reply(self, key, message_name, text, chat_message_name):
        self._check("record_reply")
        await conversation_log.record_reply(self.db, key, message_name, text, chat_message_name)

    async def finish_user_message(self, key, message_name, text, status, error):
        self._check("finish_user_message")
        await conversation_log.finish_user_message(self.db, key, message_name, text, status, error)


@pytest.fixture(autouse=True)
def fake_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    @asynccontextmanager
    async def open_graph():
        yield FakeGraph()

    monkeypatch.setattr(conversation, "open_graph", open_graph)


@pytest.fixture
def reply(monkeypatch: pytest.MonkeyPatch) -> None:
    async def run_turn(graph, ctx, message_name, text, from_checkpoint=None) -> str:
        return "hello Ann"

    monkeypatch.setattr(conversation, "run_turn", run_turn)


@pytest.fixture
def model_down(monkeypatch: pytest.MonkeyPatch) -> None:
    async def run_turn(graph, ctx, message_name, text, from_checkpoint=None) -> str:
        raise RuntimeError("model down")

    monkeypatch.setattr(conversation, "run_turn", run_turn)


async def _messages(db: AsyncSession) -> dict[str, Message]:
    rows = (await db.scalars(select(Message))).all()
    return {m.external_id: m for m in rows}


async def test_conversation_is_created_once_per_thread(db_session: AsyncSession, reply) -> None:
    log = SessionLog(db_session)

    await conversation.process_item(FakeChat(), log, ITEM)
    await conversation.process_item(
        FakeChat(), log, ITEM.model_copy(update={"message_name": "spaces/A/messages/2"})
    )

    [row] = (await db_session.scalars(select(Conversation))).all()
    assert (row.channel, row.thread_id) == ("google_chat", "gchat:spaces/A:users/1")
    assert (row.space, row.external_user, row.display_name) == ("spaces/A", "users/1", "Ann")
    assert len(await _messages(db_session)) == 4


async def test_turn_records_the_user_message_and_the_reply(db_session: AsyncSession, reply) -> None:
    chat = FakeChat()

    await conversation.process_item(chat, SessionLog(db_session), ITEM)

    rows = await _messages(db_session)
    user, assistant = rows[ITEM.message_name], rows[f"{ITEM.message_name}#reply"]
    assert (user.role, user.content, user.status) == (
        MessageRole.USER,
        "hi",
        MessageStatus.ANSWERED,
    )
    assert user.error is None
    assert (assistant.role, assistant.content, assistant.status) == (
        MessageRole.ASSISTANT,
        "hello Ann",
        None,
    )
    assert assistant.chat_message_name == "spaces/A/messages/1"


async def test_failed_turn_marks_the_message_failed_and_logs_the_apology(
    db_session: AsyncSession, model_down
) -> None:
    await conversation.process_item(FakeChat(), SessionLog(db_session), ITEM)

    rows = await _messages(db_session)
    user, assistant = rows[ITEM.message_name], rows[f"{ITEM.message_name}#reply"]
    assert user.status == MessageStatus.FAILED
    assert user.error == "RuntimeError: model down"
    assert assistant.content == FAILURE_REPLY


async def test_expired_item_that_was_never_logged_is_created_as_expired(
    db_session: AsyncSession, model_down
) -> None:
    stale = ITEM.model_copy(update={"enqueued_at": 0})
    # the first write fails, so only finish_user_message can create the user row
    log = SessionLog(db_session, fail=frozenset({"record_user_message"}))

    await conversation.process_item(FakeChat(), log, stale)

    rows = await _messages(db_session)
    user, assistant = rows[ITEM.message_name], rows[f"{ITEM.message_name}#reply"]
    assert (user.content, user.status) == ("hi", MessageStatus.EXPIRED)
    assert user.error is not None and "waited" in user.error
    assert assistant.content == FAILURE_REPLY


async def test_redelivered_item_does_not_duplicate_rows(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    answers = iter(["first", "second"])

    async def run_turn(graph, ctx, message_name, text, from_checkpoint=None) -> str:
        return next(answers)

    monkeypatch.setattr(conversation, "run_turn", run_turn)
    log = SessionLog(db_session)

    await conversation.process_item(FakeChat(), log, ITEM)
    await conversation.process_item(FakeChat(), log, ITEM)

    rows = await _messages(db_session)
    assert len(rows) == 2
    assert rows[f"{ITEM.message_name}#reply"].content == "second"
    assert rows[ITEM.message_name].status == MessageStatus.ANSWERED


async def test_redelivery_never_resets_an_answered_message_to_pending(
    db_session: AsyncSession, reply
) -> None:
    log = SessionLog(db_session)
    await conversation.process_item(FakeChat(), log, ITEM)
    key = ConversationKey("google_chat", "gchat:spaces/A:users/1", "spaces/A", "users/1", "Ann")

    await log.record_user_message(key, ITEM.message_name, "hi")

    assert (await _messages(db_session))[ITEM.message_name].status == MessageStatus.ANSWERED


async def test_failing_first_write_does_not_block_the_reply(
    db_session: AsyncSession, reply
) -> None:
    chat = FakeChat()
    log = SessionLog(db_session, fail=frozenset({"record_user_message"}))

    await conversation.process_item(chat, log, ITEM)

    assert chat.sent == [("spaces/A", "hello Ann")]
    rows = await _messages(db_session)
    assert rows[ITEM.message_name].status == MessageStatus.ANSWERED
    assert rows[f"{ITEM.message_name}#reply"].content == "hello Ann"
    assert len((await db_session.scalars(select(Conversation))).all()) == 1


async def test_failing_last_write_does_not_block_the_reply(db_session: AsyncSession, reply) -> None:
    chat = FakeChat()
    log = SessionLog(db_session, fail=frozenset({"finish_user_message"}))

    await conversation.process_item(chat, log, ITEM)

    assert chat.sent == [("spaces/A", "hello Ann")]
    assert (await _messages(db_session))[ITEM.message_name].status == MessageStatus.PENDING


async def test_failing_log_does_not_replace_the_reply_with_the_apology(
    db_session: AsyncSession, reply
) -> None:
    chat = FakeChat()
    log = SessionLog(db_session, fail=frozenset({"record_reply", "finish_user_message"}))

    await conversation.process_item(chat, log, ITEM)

    assert chat.sent == [("spaces/A", "hello Ann")]
