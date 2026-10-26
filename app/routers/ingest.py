from fastapi import APIRouter

from app.core.celery_app import dispatch
from app.core.deps import VerifiedChatEvent, VerifiedChatSender
from app.core.logger import logger
from app.core.trace import trace_id
from app.services import google_chat as google_chat_service
from app.tasks.google_chat import process_chat_event

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/google-chat")
async def google_chat(event: VerifiedChatEvent, sender: VerifiedChatSender) -> dict:
    chat = event.chat
    if not google_chat_service.is_queued(chat):
        return {}  # neither a message nor a command (e.g. added to a space): nothing to queue
    if sender is None:
        user = chat.user
        domain = (user.email or "").rpartition("@")[2] if user else ""
        logger.info(
            f"google chat sender rejected chat_user={user.name if user else None} domain={domain}"
        )
        return google_chat_service.reply(google_chat_service.NO_ACCESS_REPLY)
    logger.info(f"google chat sender user_id={sender}")
    # only the chat payload is enqueued, never the ID token
    await dispatch(
        process_chat_event,
        chat.model_dump(mode="json", by_alias=True, exclude_unset=True),
        trace_id.get(),
    )
    return google_chat_service.reply(google_chat_service.ACK)
