from app.core.logger import logger
from app.schemas.google_chat import ChatPayload

ACK = "Got it"


def reply(text: str) -> dict:
    """Chat reply body for a Workspace add-on app (not the legacy {"text": ...} shape)."""
    return {
        "hostAppDataAction": {
            "chatDataAction": {"createMessageAction": {"message": {"text": text}}}
        }
    }


async def handle_event(chat: ChatPayload) -> None:
    """Runs in the worker. For now it only logs the message; ingestion comes later."""
    payload = chat.message_payload
    if payload is None:  # e.g. added to a space: nothing to process
        return
    msg = payload.message
    sender = msg.sender.email if msg.sender else None
    text = (msg.argument_text or msg.text).strip()
    logger.info(f"google chat message space={payload.space.name} sender={sender} text={text!r}")
