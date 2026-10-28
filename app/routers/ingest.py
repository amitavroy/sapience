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
        return {}  # not a message, a command or a click (e.g. added to a space): nothing to queue
    click = google_chat_service.is_click(chat)
    if sender is None:
        user = chat.user
        domain = (user.email or "").rpartition("@")[2] if user else ""
        logger.info(
            f"google chat sender rejected chat_user={user.name if user else None} domain={domain}"
        )
        # a click has no message to reply to; the card stays as it is
        return {} if click else google_chat_service.reply(google_chat_service.NO_ACCESS_REPLY)
    logger.info(f"google chat sender user_id={sender}")
    # only the chat payload is enqueued, never the ID token
    payload = chat.model_dump(mode="json", by_alias=True, exclude_unset=True)
    parameters = event.common_event_object.parameters if event.common_event_object else {}
    if click:
        if not google_chat_service.is_asker(chat, parameters):
            logger.info(f"google chat click from another user, ignored chat_user={chat.user.name}")
            return {}  # not their question: no update, nothing queued
        # the button's parameters sit outside `chat`, so they travel inside it
        payload["actionParameters"] = parameters
    await dispatch(process_chat_event, payload, trace_id.get(), sender)
    if click:
        return google_chat_service.click_response(parameters)
    return google_chat_service.reply(google_chat_service.ACK)
