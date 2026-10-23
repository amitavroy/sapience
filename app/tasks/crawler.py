import asyncio
import random
import time

from app.core.celery_app import celery_app
from app.core.logger import logger
from app.models.document import DocumentStatus
from app.services import crawler as crawler_service
from app.services import ingest, web_extractor
from app.tasks import embedding as embedding_tasks

RETRY_DELAYS = (3, 5, 15)  # seconds before failure retries 1, 2 and 3
MAX_RATE_LIMIT_REQUEUES = 60  # only reached when one host is flooded with tasks


# max_retries=None: the bound is RETRY_DELAYS, counted in `attempt` (not self.request.retries)
@celery_app.task(bind=True, max_retries=None)
def crawl_url(
    self, url: str, trace_id: str, collection_id: int, attempt: int = 0, requeues: int = 0
) -> None:
    with logger.contextualize(trace_id=trace_id, job="crawl_url"):
        started = time.monotonic()
        try:
            # SYNC-EXCEPTION: Celery task bodies are sync; asyncio.run drives the async work
            _outcome, doc, stored = asyncio.run(ingest.crawl_and_store(url, collection_id))
        except crawler_service.RateLimited:
            # not a failure: re-queue without using up the failure retries
            if requeues >= MAX_RATE_LIMIT_REQUEUES:
                logger.warning("giving up on {}: rate limited {} times", url, requeues)
                return
            raise self.retry(
                # jitter keeps many queued tasks for one host from retrying in lockstep
                countdown=random.uniform(1, 3),
                # url, trace_id and collection_id go in args: delay() queued them positionally,
                # and passing them as kwargs too fails with "multiple values for argument"
                args=(url, trace_id, collection_id),
                kwargs={"attempt": attempt, "requeues": requeues + 1},
            ) from None
        except web_extractor.ExtractionError as exc:
            if exc.retryable and attempt < len(RETRY_DELAYS):
                delay = RETRY_DELAYS[attempt]
                logger.info("retrying {} in {}s: {}", url, delay, exc.reason.value)
                # raised here, outside asyncio.run, so the task goes back on the queue
                raise self.retry(
                    countdown=delay,
                    args=(url, trace_id, collection_id),
                    kwargs={"attempt": attempt + 1, "requeues": requeues},
                ) from exc
            logger.warning(
                "crawl failed for {}: {} (status {}, attempts {})",
                url,
                exc.reason.value,
                exc.status_code,
                attempt + 1,
            )
            return

        # robots.txt is the only reason for no document; checking the values also narrows the types
        if doc is None or stored is None:
            logger.info("skipped: disallowed by robots.txt ({})", url)
            return

        duration_ms = round((time.monotonic() - started) * 1000)
        logger.info(
            "crawled {} source_uri={} status={} title={!r} blocks={} sections={} links={} "
            "text_length={} content_hash={} duration_ms={}",
            url,
            doc.source_uri,
            doc.status_code,
            doc.title,
            len(doc.blocks),
            len(doc.sections),
            len(doc.links),
            len(doc.text()),
            doc.content_hash,
            duration_ms,
        )
        logger.debug("extracted document: {}", doc.model_dump_json(exclude_defaults=True))

        match stored.outcome:
            case ingest.StoreOutcome.STORED:
                logger.info(
                    "stored document {} chunks={} tokens={}",
                    stored.document_id,
                    stored.chunks,
                    stored.tokens,
                )
            case ingest.StoreOutcome.DUPLICATE:
                logger.info("duplicate of document {}", stored.document_id)
            case ingest.StoreOutcome.COLLECTION_MISSING:
                logger.warning("collection {} not found", collection_id)

        # a pending duplicate means an earlier run stored the page but may have died before
        # enqueueing; embedding is idempotent, so enqueueing again is safe
        if stored.outcome is ingest.StoreOutcome.STORED or (
            stored.outcome is ingest.StoreOutcome.DUPLICATE
            and stored.status == DocumentStatus.PENDING
        ):
            embedding_tasks.embed_document.delay(stored.document_id, trace_id)
