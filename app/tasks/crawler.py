import asyncio
import random
import time

from app.core.celery_app import celery_app
from app.core.logger import logger
from app.services import crawler as crawler_service
from app.services import web_extractor

RETRY_DELAYS = (3, 5, 15)  # seconds before failure retries 1, 2 and 3
MAX_RATE_LIMIT_REQUEUES = 60  # only reached when one host is flooded with tasks


# max_retries=None: the bound is RETRY_DELAYS, counted in `attempt` (not self.request.retries)
@celery_app.task(bind=True, max_retries=None)
def crawl_url(self, url: str, trace_id: str, attempt: int = 0, requeues: int = 0) -> None:
    with logger.contextualize(trace_id=trace_id, job="crawl_url"):
        started = time.monotonic()
        try:
            # SYNC-EXCEPTION: Celery task bodies are sync; asyncio.run drives the async work
            outcome, doc = asyncio.run(crawler_service.crawl_page(url))
        except crawler_service.RateLimited:
            # not a failure: re-queue without using up the failure retries
            if requeues >= MAX_RATE_LIMIT_REQUEUES:
                logger.warning("giving up on {}: rate limited {} times", url, requeues)
                return
            raise self.retry(
                # jitter keeps many queued tasks for one host from retrying in lockstep
                countdown=random.uniform(1, 3),
                kwargs={
                    "url": url,
                    "trace_id": trace_id,
                    "attempt": attempt,
                    "requeues": requeues + 1,
                },
            ) from None
        except web_extractor.ExtractionError as exc:
            if exc.retryable and attempt < len(RETRY_DELAYS):
                delay = RETRY_DELAYS[attempt]
                logger.info("retrying {} in {}s: {}", url, delay, exc.reason.value)
                # raised here, outside asyncio.run, so the task goes back on the queue
                raise self.retry(
                    countdown=delay,
                    kwargs={
                        "url": url,
                        "trace_id": trace_id,
                        "attempt": attempt + 1,
                        "requeues": requeues,
                    },
                ) from exc
            logger.warning(
                "crawl failed for {}: {} (status {}, attempts {})",
                url,
                exc.reason.value,
                exc.status_code,
                attempt + 1,
            )
            return

        if outcome is crawler_service.CrawlOutcome.ROBOTS_DISALLOWED:
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
