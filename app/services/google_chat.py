from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

from app.agent.state import ConversationContext
from app.core.config import settings
from app.core.google_chat_client import GoogleChatClient
from app.core.logger import logger
from app.schemas.google_chat import AppCommandPayload, ChatPayload, MessagePayload
from app.services import conversation

ACK = "Got it"
DM_REPLY = "I only work in spaces. Mention me in a space."
EMPTY_REPLY = "Ask me something after the mention."
FAILURE_REPLY = "Sorry, something went wrong. Please try again."


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
async def _open_chat_client() -> AsyncIterator[GoogleChatClient]:
    # the worker has no app lifespan, so it opens its own client for the task
    async with httpx.AsyncClient(timeout=10) as http:
        yield GoogleChatClient(http, settings.google_chat_credentials_file)


async def _handle_mention(payload: MessagePayload) -> None:
    """Answer a mention in a space through the conversation agent."""
    msg = payload.message
    space = payload.space.name
    sender = msg.sender.email if msg.sender else None
    text = (msg.argument_text or msg.text).strip()
    logger.info(f"google chat message space={space} sender={sender} text={text!r}")
    if msg.sender is None:  # no stable user id to key the conversation on
        return

    async with _open_chat_client() as chat:
        if payload.space.type == "DM":
            await send_message(chat, space, DM_REPLY)
        elif not text:
            await send_message(chat, space, EMPTY_REPLY)
        else:
            ctx = ConversationContext(
                space=space,
                user=msg.sender.name,
                display_name=msg.sender.display_name or msg.sender.name,
            )
            await _answer(chat, ctx, msg.name, text)


async def _answer(
    chat: GoogleChatClient, ctx: ConversationContext, message: str, text: str
) -> None:
    try:
        async with conversation.open_graph() as graph:
            answer = await conversation.run_turn(graph, ctx, message, text)
        await send_message(chat, ctx.space, answer)
    except Exception as e:
        # log the type and message only; never the request, which can carry credentials
        logger.error(f"conversation turn failed space={ctx.space}: {type(e).__name__}: {e}")
        try:
            await send_message(chat, ctx.space, FAILURE_REPLY)
        except Exception as e2:
            logger.error(f"could not post the failure reply: {type(e2).__name__}: {e2}")


async def _handle_command(payload: AppCommandPayload) -> None:
    """For now it only logs the command; ingestion of /add-knowledge comes later."""
    msg = payload.message
    sender = msg.sender.email if msg.sender else None
    text = (msg.argument_text or msg.text).strip()
    command_id = payload.app_command_metadata.app_command_id
    logger.info(
        f"google chat command id={command_id} space={payload.space.name} "
        f"sender={sender} text={text!r}"
    )
