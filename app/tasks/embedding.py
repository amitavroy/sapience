import asyncio

from app.core.celery_app import celery_app
from app.core.logger import logger
from app.db.session import task_session
from app.models.document import Document, DocumentStatus
from app.services.embedding import EmbeddingError, get_embedder, run_embedding

RETRY_DELAYS = (5, 15, 60)  # seconds before failure retries 1, 2 and 3


# max_retries=None: the bound is RETRY_DELAYS, counted in `attempt` (not self.request.retries)
@celery_app.task(bind=True, max_retries=None)
def embed_document(self, document_id: int, trace_id: str, attempt: int = 0) -> None:
    with logger.contextualize(trace_id=trace_id, job="embed_document"):
        try:
            # SYNC-EXCEPTION: Celery task bodies are sync; asyncio.run drives the async work
            asyncio.run(_run(document_id))
        except EmbeddingError as exc:
            if exc.retryable and attempt < len(RETRY_DELAYS):
                delay = RETRY_DELAYS[attempt]
                logger.info("retrying embedding of document {} in {}s: {}", document_id, delay, exc)
                # raised here, outside asyncio.run, so the task goes back on the queue
                raise self.retry(
                    countdown=delay,
                    args=(document_id, trace_id),
                    kwargs={"attempt": attempt + 1},
                ) from exc
            asyncio.run(_mark_failed(document_id, str(exc)))
            logger.warning("embedding failed for document {}: {}", document_id, exc)


async def _run(document_id: int) -> None:
    # one client per run: Celery tasks have no lifespan to share one
    async with task_session() as db:
        await run_embedding(db, document_id, get_embedder())


async def _mark_failed(document_id: int, error: str) -> None:
    async with task_session() as db:
        document = await db.get(Document, document_id)
        if document is not None:
            document.status = DocumentStatus.FAILED
            document.error = error
            await db.commit()
