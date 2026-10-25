from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Message, MessageRole, MessageStatus
from app.services import conversation, conversation_log
from app.services.conversation_log import ConversationKey
from app.services.conversation_queue import QueueItem
from app.services.google_chat import FAILURE_REPLY, RESET_REPLY
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

    async def clear_messages(self, key):
        self._check("clear_messages")
        await conversation_log.clear_messages(self.db, key)


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


# /reset: the log half (clear_messages) and its wiring in _process_reset

RESET = ITEM.model_copy(update={"kind": "reset", "message_name": "spaces/A/messages/reset-1"})


def _key(
    user: str = "users/1", space: str = "spaces/A", owner: str | None = None
) -> ConversationKey:
    return ConversationKey(
        channel="google_chat",
        thread_id=conversation.thread_id(space, user),
        space=space,
        external_user=owner if owner is not None else user,
        display_name=user,
    )


async def _seed(db: AsyncSession, key: ConversationKey, name: str) -> None:
    await conversation_log.record_user_message(db, key, name, "hello")
    await conversation_log.record_reply(db, key, name, "hi there", f"{name}/chat")


async def _by_thread(db: AsyncSession) -> dict[str, list[str]]:
    rows = (
        await db.execute(select(Conversation.thread_id, Message.external_id).join(Message))
    ).all()
    grouped: dict[str, list[str]] = {}
    for thread, external_id in rows:
        grouped.setdefault(thread, []).append(external_id)
    return grouped


class RecordingCheckpointer:
    """Stands in for the checkpointer behind reset(); `fail` makes the delete raise."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.deleted: list[str] = []

    async def adelete_thread(self, thread_id: str) -> None:
        if self.fail:
            raise ConnectionError("checkpoint db down")
        self.deleted.append(thread_id)


@pytest.fixture
def checkpointer(monkeypatch: pytest.MonkeyPatch) -> RecordingCheckpointer:
    saver = RecordingCheckpointer()

    @asynccontextmanager
    async def open_checkpointer():
        yield saver

    monkeypatch.setattr(conversation, "open_checkpointer", open_checkpointer)
    return saver


async def test_reset_clears_the_owners_messages_and_checkpoint_and_logs_the_reply(
    db_session: AsyncSession, checkpointer: RecordingCheckpointer
) -> None:
    await _seed(db_session, _key(), "spaces/A/messages/1")
    chat = FakeChat()

    await conversation.process_item(chat, SessionLog(db_session), RESET)

    assert chat.sent == [("spaces/A", RESET_REPLY)]
    assert checkpointer.deleted == ["gchat:spaces/A:users/1"]
    [row] = (await db_session.scalars(select(Message))).all()
    assert (row.role, row.content, row.status) == (MessageRole.ASSISTANT, RESET_REPLY, None)
    assert row.external_id == f"{RESET.message_name}#reply"
    assert row.chat_message_name == "spaces/A/messages/1"
    assert len((await db_session.scalars(select(Conversation))).all()) == 1


async def test_reset_touches_only_the_owners_data(
    db_session: AsyncSession, checkpointer: RecordingCheckpointer
) -> None:
    await _seed(db_session, _key("users/1"), "spaces/A/messages/a1")
    await _seed(db_session, _key("users/2"), "spaces/A/messages/b1")
    await _seed(db_session, _key("users/1", "spaces/B"), "spaces/B/messages/a1")

    await conversation.process_item(FakeChat(), SessionLog(db_session), RESET)

    grouped = await _by_thread(db_session)
    assert grouped["gchat:spaces/A:users/1"] == [f"{RESET.message_name}#reply"]
    assert len(grouped["gchat:spaces/A:users/2"]) == 2
    assert len(grouped["gchat:spaces/B:users/1"]) == 2
    assert checkpointer.deleted == ["gchat:spaces/A:users/1"]


async def test_clear_messages_needs_the_stored_owner(db_session: AsyncSession) -> None:
    await _seed(db_session, _key("users/1"), "spaces/A/messages/1")
    thread = conversation.thread_id("spaces/A", "users/1")

    # the thread id is users/1's, the claimed owner is not
    await conversation_log.clear_messages(db_session, _key("users/1", owner="users/2"))
    assert len((await _by_thread(db_session))[thread]) == 2

    # no owner at all must not match a row either
    stored = (await db_session.scalars(select(Conversation))).one()
    stored.external_user = None
    await db_session.commit()
    no_owner = ConversationKey("google_chat", thread, "spaces/A", None, "x")
    await conversation_log.clear_messages(db_session, no_owner)
    assert len((await _by_thread(db_session))[thread]) == 2


async def test_reset_item_names_no_other_user_or_conversation(
    db_session: AsyncSession, checkpointer: RecordingCheckpointer
) -> None:
    assert not {"target", "target_user", "thread_id", "conversation_id"} & set(
        QueueItem.model_fields
    )
    await _seed(db_session, _key("users/2"), "spaces/A/messages/b1")
    # the command text names another user; only the sender's conversation is addressed
    item = RESET.model_copy(update={"text": "users/2"})

    await conversation.process_item(FakeChat(), SessionLog(db_session), item)

    assert len((await _by_thread(db_session))["gchat:spaces/A:users/2"]) == 2
    assert checkpointer.deleted == ["gchat:spaces/A:users/1"]


async def test_reset_before_any_conversation_still_posts_and_records(
    db_session: AsyncSession, checkpointer: RecordingCheckpointer
) -> None:
    chat = FakeChat()

    await conversation.process_item(chat, SessionLog(db_session), RESET)

    assert chat.sent == [("spaces/A", RESET_REPLY)]
    [row] = (await db_session.scalars(select(Message))).all()
    assert row.content == RESET_REPLY


@pytest.mark.parametrize("broken", ["checkpoint", "messages"])
async def test_failed_clear_apologises_and_the_next_reset_succeeds(
    db_session: AsyncSession,
    checkpointer: RecordingCheckpointer,
    broken: str,
) -> None:
    await _seed(db_session, _key(), "spaces/A/messages/1")
    checkpointer.fail = broken == "checkpoint"
    log = SessionLog(db_session, fail=frozenset({"clear_messages"} if broken == "messages" else ()))
    chat = FakeChat()

    await conversation.process_item(chat, log, RESET)

    assert chat.sent == [("spaces/A", FAILURE_REPLY)]
    rows = await _messages(db_session)
    assert set(rows) == {"spaces/A/messages/1", "spaces/A/messages/1#reply"}  # nothing recorded
    if broken == "checkpoint":
        assert len(rows) == 2  # the messages were not touched either

    checkpointer.fail = False
    await conversation.process_item(chat, SessionLog(db_session), RESET)

    assert chat.sent[-1] == ("spaces/A", RESET_REPLY)
    assert set(await _messages(db_session)) == {f"{RESET.message_name}#reply"}


async def test_retried_reset_does_not_duplicate_the_reply_row(
    db_session: AsyncSession, checkpointer: RecordingCheckpointer
) -> None:
    log = SessionLog(db_session)

    await conversation.process_item(FakeChat(), log, RESET)
    await conversation.process_item(FakeChat(), log, RESET)

    assert len((await db_session.scalars(select(Message))).all()) == 1
