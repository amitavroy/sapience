from app.core.logger import logger
from app.schemas.google_chat import AppCommandPayload, ChatPayload, MessagePayload

ACK = "Got it"


def reply(text: str) -> dict:
    """Chat reply body for a Workspace add-on app (not the legacy {"text": ...} shape)."""
    return {
        "hostAppDataAction": {
            "chatDataAction": {"createMessageAction": {"message": {"text": text}}}
        }
    }


async def handle_event(chat: ChatPayload) -> None:
    """Runs in the worker. Decides what kind of event this is and delegates."""
    if chat.message_payload is not None:
        await _handle_mention(chat.message_payload)
    elif chat.app_command_payload is not None:
        await _handle_command(chat.app_command_payload)
    # anything else (e.g. added to a space): nothing to process


async def _handle_mention(payload: MessagePayload) -> None:
    """For now it only logs the message; ingestion comes later."""
    msg = payload.message
    sender = msg.sender.email if msg.sender else None
    text = (msg.argument_text or msg.text).strip()
    logger.info(f"google chat message space={payload.space.name} sender={sender} text={text!r}")


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
