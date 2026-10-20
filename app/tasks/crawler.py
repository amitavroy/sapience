import asyncio
import time

import httpx

from app.core.celery_app import celery_app
from app.core.logger import logger
from app.schemas.extracted_document import ExtractedDocument
from app.services import web_extractor


async def _extract(url: str) -> ExtractedDocument:
    # Celery tasks have no lifespan, so each run owns its client
    async with httpx.AsyncClient() as client:
        return await web_extractor.extract_url(client, url)


@celery_app.task
def crawl_url(url: str, trace_id: str) -> None:
    with logger.contextualize(trace_id=trace_id, job="crawl_url"):
        started = time.monotonic()
        try:
            # SYNC-EXCEPTION: Celery task bodies are sync; asyncio.run drives the async work
            doc = asyncio.run(_extract(url))
        except web_extractor.ExtractionError as exc:
            logger.warning(
                "crawl failed for {}: {} (status {})", url, exc.reason.value, exc.status_code
            )
            return

        duration_ms = round((time.monotonic() - started) * 1000)
        logger.info(
            "crawled {} source_uri={} status={} title={!r} blocks={} text_length={} "
            "content_hash={} duration_ms={}",
            url,
            doc.source_uri,
            doc.status_code,
            doc.title,
            len(doc.blocks),
            len(doc.text()),
            doc.content_hash,
            duration_ms,
        )
        logger.debug("extracted document: {}", doc.model_dump_json(exclude_defaults=True))
