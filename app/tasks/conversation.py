import asyncio

from app.core.celery_app import celery_app
from app.core.logger import logger
from app.core.trace import trace_id as trace_var
from app.db.session import task_session
from app.models.conversation import MessageStatus
from app.services import conversation as conversation_service
from app.services import conversation_log, retrieval
from app.services.conversation_log import ConversationKey
from app.services.embedding import Embedder, get_embedder
from app.services.retrieval import RetrievedChunk


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


class TaskKnowledgeSearch:
    """Embeds first, then opens a session for the one query, so none is held across the call."""

    def __init__(self, embedder: Embedder | None = None) -> None:
        self._embedder = embedder
        # the probe's vectors, by query text: the deep search on the clear path reuses the first
        # one. Each probe replaces them, so they never outlive the turn that made them.
        self._vectors: dict[str, list[float]] = {}

    def _get_embedder(self) -> Embedder:
        if self._embedder is None:
            self._embedder = get_embedder()  # built on first use: a bad key fails the turn
        return self._embedder

    async def probe(self, user_id: int, queries: list[str]) -> list[RetrievedChunk]:
        result = await self._get_embedder().embed(queries)
        self._vectors = dict(zip(queries, result.vectors, strict=True))
        async with task_session() as db:
            return await retrieval.probe(db, user_id, result.vectors)

    async def deep_search(
        self, user_id: int, query: str, doc_ids: list[int] | None
    ) -> list[RetrievedChunk]:
        vector = self._vectors.get(query)
        if vector is None:
            vector = (await self._get_embedder().embed([query])).vectors[0]
        async with task_session() as db:
            return await retrieval.deep_search(db, user_id, vector, doc_ids)


@celery_app.task
def drain_conversation(space: str, user: str, trace_id: str) -> None:
    with logger.contextualize(trace_id=trace_id, job="drain_conversation"):
        token = trace_var.set(trace_id)
        try:
            # SYNC-EXCEPTION: Celery task bodies are sync; asyncio.run drives the async work
            asyncio.run(
                conversation_service.drain(
                    space, user, TaskConversationLog(), TaskKnowledgeSearch()
                )
            )
        finally:
            trace_var.reset(token)
