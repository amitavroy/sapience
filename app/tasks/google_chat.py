import asyncio

from app.core.celery_app import celery_app
from app.core.logger import logger
from app.core.trace import trace_id as trace_var
from app.schemas.google_chat import ChatPayload
from app.services import google_chat as google_chat_service


@celery_app.task
def process_chat_event(chat: dict, trace_id: str, app_user_id: int) -> None:
    with logger.contextualize(trace_id=trace_id, job="process_chat_event"):
        token = trace_var.set(trace_id)  # services read it, e.g. to pass it on to the drain
        try:
            # SYNC-EXCEPTION: Celery task bodies are sync; asyncio.run drives the async work
            asyncio.run(
                google_chat_service.handle_event(ChatPayload.model_validate(chat), app_user_id)
            )
        finally:
            trace_var.reset(token)
