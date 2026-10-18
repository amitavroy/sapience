from fastapi import APIRouter

from app.core.celery_app import dispatch
from app.core.deps import VerifiedChatEvent
from app.core.trace import trace_id
from app.services import google_chat as google_chat_service
from app.tasks.google_chat import process_chat_event

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/google-chat")
async def google_chat(event: VerifiedChatEvent) -> dict:
    if event.chat is None or event.chat.message_payload is None:
        return {}  # not a message (e.g. added to a space): nothing to ack or queue
    # only the chat payload is enqueued, never the ID token
    await dispatch(
        process_chat_event,
        event.chat.model_dump(mode="json", by_alias=True, exclude_unset=True),
        trace_id.get(),
    )
    return google_chat_service.reply(google_chat_service.ACK)
