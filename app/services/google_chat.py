from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

from app.core.celery_app import dispatch
from app.core.config import settings
from app.core.google_chat_client import GoogleChatClient
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


async def send_message(client: GoogleChatClient, space: str, text: str) -> str:
    name = await client.create_message(space, text)
    logger.info(f"google chat sent space={space} message={name}")
    return name


async def handle_event(chat: ChatPayload) -> None:
    """Runs in the worker. Decides what kind of event this is and delegates."""
    if chat.message_payload is not None:
        await _handle_mention(chat.message_payload)
    elif chat.app_command_payload is not None:
        await _handle_command(chat.app_command_payload)
    # anything else (e.g. added to a space): nothing to process


@asynccontextmanager
async def open_chat_client() -> AsyncIterator[GoogleChatClient]:
    # the worker has no app lifespan, so it opens its own client for the task
    async with httpx.AsyncClient(timeout=10) as http:
        yield GoogleChatClient(http, settings.google_chat_credentials_file)


async def _handle_mention(payload: MessagePayload) -> None:
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
        email=msg.sender.email,
        trace_id=trace_id.get(),
    )
    async with conversation_queue.open_redis() as redis:
        queued = await conversation_queue.enqueue(redis, item)
    # dispatch even for a duplicate event: the first delivery may have died before dispatching,
    # and a drain with nothing to do (or one already running) is harmless
    logger.info(f"conversation message queued={queued} space={space} message={msg.name}")
    await dispatch(conversation_tasks.drain_conversation, space, item.user, item.trace_id)


async def _handle_command(payload: AppCommandPayload) -> None:
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
        trace_id=trace_id.get(),
    )
    # queued like a message, so a turn that is mid-run is not raced and earlier messages
    # are answered before the memory is cleared
    async with conversation_queue.open_redis() as redis:
        queued = await conversation_queue.enqueue(redis, item)
    logger.info(f"conversation reset queued={queued} space={space} message={msg.name}")
    await dispatch(conversation_tasks.drain_conversation, space, item.user, item.trace_id)
