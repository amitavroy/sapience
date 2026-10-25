import asyncio

from app.core.celery_app import celery_app
from app.core.logger import logger
from app.core.trace import trace_id as trace_var
from app.db.session import task_session
from app.models.conversation import MessageStatus
from app.services import conversation as conversation_service
from app.services import conversation_log
from app.services.conversation_log import ConversationKey


class TaskConversationLog:
    """Each write opens its own short session, so none is held across the LLM or Chat call."""

    async def record_user_message(self, key: ConversationKey, message_name: str, text: str) -> None:
        async with task_session() as db:
            await conversation_log.record_user_message(db, key, message_name, text)

    async def record_reply(
        self,
        key: ConversationKey,
        message_name: str,
        text: str,
        chat_message_name: str | None,
    ) -> None:
        async with task_session() as db:
            await conversation_log.record_reply(db, key, message_name, text, chat_message_name)

    async def finish_user_message(
        self,
        key: ConversationKey,
        message_name: str,
        text: str,
        status: MessageStatus,
        error: str | None,
    ) -> None:
        async with task_session() as db:
            await conversation_log.finish_user_message(db, key, message_name, text, status, error)

    async def clear_messages(self, key: ConversationKey) -> None:
        async with task_session() as db:
            await conversation_log.clear_messages(db, key)


@celery_app.task
def drain_conversation(space: str, user: str, trace_id: str) -> None:
    with logger.contextualize(trace_id=trace_id, job="drain_conversation"):
        token = trace_var.set(trace_id)
        try:
            # SYNC-EXCEPTION: Celery task bodies are sync; asyncio.run drives the async work
            asyncio.run(conversation_service.drain(space, user, TaskConversationLog()))
        finally:
            trace_var.reset(token)
