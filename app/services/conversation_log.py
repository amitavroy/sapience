from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Message, MessageRole, MessageStatus


@dataclass(frozen=True)
class ConversationKey:
    """Identifies a conversation across channels; every log write finds or creates it."""

    channel: str
    thread_id: str
    space: str | None
    external_user: str | None
    display_name: str


class ConversationLog(Protocol):
    """What the drain needs from the log, without a session (the entry point supplies it)."""

    async def record_user_message(
        self, key: ConversationKey, message_name: str, text: str
    ) -> None: ...

    async def record_reply(
        self,
        key: ConversationKey,
        message_name: str,
        text: str,
        chat_message_name: str | None,
    ) -> None: ...

    async def finish_user_message(
        self,
        key: ConversationKey,
        message_name: str,
        text: str,
        status: MessageStatus,
        error: str | None,
    ) -> None: ...


def reply_external_id(message_name: str) -> str:
    return f"{message_name}#reply"


async def _find_conversation(db: AsyncSession, key: ConversationKey) -> Conversation | None:
    return await db.scalar(
        select(Conversation).where(
            Conversation.channel == key.channel, Conversation.thread_id == key.thread_id
        )
    )


async def _get_or_create_conversation(db: AsyncSession, key: ConversationKey) -> Conversation:
    if (conversation := await _find_conversation(db, key)) is not None:
        return conversation
    conversation = Conversation(
        channel=key.channel,
        thread_id=key.thread_id,
        space=key.space,
        external_user=key.external_user,
        display_name=key.display_name,
    )
    try:
        # savepoint, so losing a race on the unique constraint keeps the outer transaction usable
        async with db.begin_nested():
            db.add(conversation)
    except IntegrityError:
        existing = await _find_conversation(db, key)
        if existing is None:
            raise
        return existing
    return conversation


async def _find_message(db: AsyncSession, conversation_id: int, external_id: str) -> Message | None:
    return await db.scalar(
        select(Message).where(
            Message.conversation_id == conversation_id, Message.external_id == external_id
        )
    )


async def _get_or_create_message(
    db: AsyncSession,
    conversation: Conversation,
    external_id: str,
    role: MessageRole,
    content: str,
    status: MessageStatus | None,
) -> tuple[Message, bool]:
    """Return the row for `external_id` and whether this call created it."""
    if (existing := await _find_message(db, conversation.id, external_id)) is not None:
        return existing, False
    message = Message(
        conversation_id=conversation.id,
        role=role,
        content=content,
        external_id=external_id,
        status=status,
    )
    try:
        async with db.begin_nested():
            db.add(message)
    except IntegrityError:
        existing = await _find_message(db, conversation.id, external_id)
        if existing is None:
            raise
        return existing, False
    return message, True


async def record_user_message(
    db: AsyncSession, key: ConversationKey, message_name: str, text: str
) -> None:
    """Insert the user's message as `pending`; a redelivered item keeps its existing row."""
    conversation = await _get_or_create_conversation(db, key)
    await _get_or_create_message(
        db, conversation, message_name, MessageRole.USER, text, MessageStatus.PENDING
    )
    conversation.last_message_at = func.now()
    await db.commit()


async def finish_user_message(
    db: AsyncSession,
    key: ConversationKey,
    message_name: str,
    text: str,
    status: MessageStatus,
    error: str | None,
) -> None:
    """Set the user message's outcome, creating the row if the first write never landed.

    The only writer of `status`: the latest outcome wins, since it is what the user last saw.
    """
    conversation = await _get_or_create_conversation(db, key)
    message, _ = await _get_or_create_message(
        db, conversation, message_name, MessageRole.USER, text, status
    )
    message.status = status
    message.error = error
    conversation.last_message_at = func.now()
    await db.commit()


async def record_reply(
    db: AsyncSession,
    key: ConversationKey,
    message_name: str,
    text: str,
    chat_message_name: str | None,
) -> None:
    """Write the one assistant row for a user message; a rerun updates it instead of adding one."""
    conversation = await _get_or_create_conversation(db, key)
    message, _ = await _get_or_create_message(
        db, conversation, reply_external_id(message_name), MessageRole.ASSISTANT, text, None
    )
    message.content = text
    message.chat_message_name = chat_message_name
    conversation.last_message_at = func.now()
    await db.commit()
