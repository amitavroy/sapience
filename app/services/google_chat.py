import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx

from app.agent.nodes.retrieval import NONE_LABEL
from app.core.celery_app import dispatch
from app.core.config import settings
from app.core.google_chat_client import GoogleChatClient, GoogleChatError
from app.core.logger import logger
from app.core.trace import trace_id
from app.schemas.google_chat import AppCommandPayload, ChatPayload, MessagePayload
from app.services import conversation_queue
from app.tasks import conversation as conversation_tasks

ACK = "Got it"
DM_REPLY = "I only work in spaces. Mention me in a space."
EMPTY_REPLY = "Ask me something after the mention."
FAILURE_REPLY = "Sorry, something went wrong. Please try again."
RESET_REPLY = "Conversation cleared."
NO_ACCESS_REPLY = "Sorry, your account can't use this bot."
NONE_OPTION = "none"
SKIPPED_NOTE = "This question was skipped."
EXPIRED_NOTE = "This question has expired."


def is_queued(chat: ChatPayload | None) -> bool:
    """A message or a command; anything else (e.g. added to a space) has nothing to queue."""
    return chat is not None and (
        chat.message_payload is not None or chat.app_command_payload is not None
    )


def reply(text: str) -> dict:
    """Chat reply body for a Workspace add-on app (not the legacy {"text": ...} shape)."""
    return {
        "hostAppDataAction": {
            "chatDataAction": {"createMessageAction": {"message": {"text": text}}}
        }
    }


_FENCE = re.compile(r"```[^\n`]*\n?(.*?)```", re.DOTALL)
_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*$", re.MULTILINE)
_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


def to_chat_markup(text: str) -> str:
    """Markdown the model writes, as the markup Chat renders (*bold*, <url|text>, plain fences).

    Code fences are copied as they are, except the language label, which Chat would show.
    """
    parts = re.split(r"(```.*?```)", text, flags=re.DOTALL)
    for i, part in enumerate(parts):
        if part.startswith("```"):
            parts[i] = _FENCE.sub(lambda m: f"```\n{m.group(1).strip(chr(10))}\n```", part)
            continue
        part = _HEADING.sub(r"*\1*", part)
        part = _BOLD.sub(lambda m: f"*{m.group(1) or m.group(2)}*", part)
        parts[i] = _LINK.sub(r"<\2|\1>", part)
    return "".join(parts)


async def send_message(client: GoogleChatClient, space: str, text: str) -> str:
    name = await client.create_message(space, to_chat_markup(text))
    logger.info(f"google chat sent space={space} message={name}")
    return name


@dataclass(frozen=True)
class ClarificationCard:
    """What the card shows: the question, up to 3 option labels, and who may answer."""

    clarification_id: str
    question: str
    labels: list[str]
    asker: str  # Chat user id (users/123); only they can answer

    @classmethod
    def from_payload(cls, payload: dict, asker: str) -> "ClarificationCard":
        """The card for the payload the graph paused with."""
        return cls(
            clarification_id=payload["clarification_id"],
            question=payload["question"],
            labels=[o["label"] for o in payload["options"]],
            asker=asker,
        )


def _button(card: ClarificationCard, label: str, option: int | str) -> dict:
    return {
        "text": label,
        "onClick": {
            "action": {
                "function": "clarification_choice",
                "parameters": [
                    {"key": "clarification_id", "value": card.clarification_id},
                    {"key": "option", "value": str(option)},
                    {"key": "label", "value": label},
                    {"key": "asker", "value": card.asker},
                ],
            }
        },
    }


async def send_card(client: GoogleChatClient, space: str, card: ClarificationCard) -> str:
    """Posts the clarifying question with one button per option plus "None of these"."""
    buttons = [_button(card, label, i) for i, label in enumerate(card.labels)]
    buttons.append(_button(card, NONE_LABEL, NONE_OPTION))
    cards_v2 = [
        {
            "cardId": card.clarification_id,
            "card": {
                "sections": [
                    {
                        "widgets": [
                            {"textParagraph": {"text": card.question}},
                            {"buttonList": {"buttons": buttons}},
                        ]
                    }
                ]
            },
        }
    ]
    name = await client.create_card_message(space, card.question, cards_v2)
    logger.info(f"google chat card sent space={space} message={name}")
    return name


async def edit_card(client: GoogleChatClient, name: str, note: str) -> None:
    """Swaps a card for one line ("skipped" / "expired"). Never raises: the reply matters more."""
    try:
        await client.update_message(name, note, None)
    except GoogleChatError as e:
        logger.warning(f"google chat card edit failed message={name} status={e.status}: {e}")


async def handle_event(chat: ChatPayload, app_user_id: int) -> None:
    """Runs in the worker. Decides what kind of event this is and delegates."""
    if chat.message_payload is not None:
        await _handle_mention(chat.message_payload, app_user_id)
    elif chat.app_command_payload is not None:
        await _handle_command(chat.app_command_payload, app_user_id)
    # anything else (e.g. added to a space): nothing to process


@asynccontextmanager
async def open_chat_client() -> AsyncIterator[GoogleChatClient]:
    # the worker has no app lifespan, so it opens its own client for the task
    async with httpx.AsyncClient(timeout=10) as http:
        yield GoogleChatClient(http, settings.google_chat_credentials_file)


async def _handle_mention(payload: MessagePayload, app_user_id: int) -> None:
    """Queue a mention for the conversation agent; DMs and empty mentions get a short reply."""
    msg = payload.message
    space = payload.space.name
    sender = msg.sender.email if msg.sender else None
    text = (msg.argument_text or msg.text).strip()
    logger.info(f"google chat message space={space} sender={sender} text={text!r}")
    if msg.sender is None:  # no stable user id to key the conversation on
        return

    if payload.space.type == "DM" or not text:
        async with open_chat_client() as chat:
            await send_message(chat, space, DM_REPLY if payload.space.type == "DM" else EMPTY_REPLY)
        return

    item = conversation_queue.QueueItem(
        space=space,
        user=msg.sender.name,
        message_name=msg.name,
        text=text,
        display_name=msg.sender.display_name or msg.sender.name,
        user_id=app_user_id,
        trace_id=trace_id.get(),
    )
    async with conversation_queue.open_redis() as redis:
        queued = await conversation_queue.enqueue(redis, item)
    # dispatch even for a duplicate event: the first delivery may have died before dispatching,
    # and a drain with nothing to do (or one already running) is harmless
    logger.info(f"conversation message queued={queued} space={space} message={msg.name}")
    await dispatch(conversation_tasks.drain_conversation, space, item.user, item.trace_id)


async def _handle_command(payload: AppCommandPayload, app_user_id: int) -> None:
    """/reset goes through the conversation queue; other commands are only logged for now."""
    msg = payload.message
    sender = msg.sender.email if msg.sender else None
    text = (msg.argument_text or msg.text).strip()
    command_id = payload.app_command_metadata.app_command_id
    space = payload.space.name
    logger.info(f"google chat command id={command_id} space={space} sender={sender} text={text!r}")
    reset_id = settings.google_chat_reset_command_id
    if not reset_id or command_id != reset_id or msg.sender is None:
        return

    item = conversation_queue.QueueItem(
        kind="reset",
        space=space,
        user=msg.sender.name,
        message_name=msg.name,
        display_name=msg.sender.display_name or msg.sender.name,
        user_id=app_user_id,
        trace_id=trace_id.get(),
    )
    # queued like a message, so a turn that is mid-run is not raced and earlier messages
    # are answered before the memory is cleared
    async with conversation_queue.open_redis() as redis:
        queued = await conversation_queue.enqueue(redis, item)
    logger.info(f"conversation reset queued={queued} space={space} message={msg.name}")
    await dispatch(conversation_tasks.drain_conversation, space, item.user, item.trace_id)
