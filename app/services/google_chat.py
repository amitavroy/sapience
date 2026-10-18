from app.core.logger import logger
from app.schemas.google_chat import ChatPayload, MessagePayload

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
    # anything else (e.g. added to a space): nothing to process


async def _handle_mention(payload: MessagePayload) -> None:
    """For now it only logs the message; ingestion comes later."""
    msg = payload.message
    sender = msg.sender.email if msg.sender else None
    text = (msg.argument_text or msg.text).strip()
    logger.info(f"google chat message space={payload.space.name} sender={sender} text={text!r}")
