import asyncio

from app.core.celery_app import celery_app
from app.core.logger import logger
from app.schemas.google_chat import ChatPayload
from app.services import google_chat as google_chat_service


@celery_app.task
def process_chat_event(chat: dict, trace_id: str) -> None:
    with logger.contextualize(trace_id=trace_id, job="process_chat_event"):
        # SYNC-EXCEPTION: Celery task bodies are sync; asyncio.run drives the async work
        asyncio.run(google_chat_service.handle_event(ChatPayload.model_validate(chat)))
