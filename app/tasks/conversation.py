import asyncio

from app.core.celery_app import celery_app
from app.core.logger import logger
from app.core.trace import trace_id as trace_var
from app.services import conversation as conversation_service


@celery_app.task
def drain_conversation(space: str, user: str, trace_id: str) -> None:
    with logger.contextualize(trace_id=trace_id, job="drain_conversation"):
        token = trace_var.set(trace_id)
        try:
            # SYNC-EXCEPTION: Celery task bodies are sync; asyncio.run drives the async work
            asyncio.run(conversation_service.drain(space, user))
        finally:
            trace_var.reset(token)
