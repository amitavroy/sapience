from enum import StrEnum
from urllib.parse import urlsplit

import httpx
from limits import parse
from limits.aio.storage import RedisStorage
from limits.aio.strategies import FixedWindowRateLimiter

from app.core.config import settings
from app.schemas.extracted_document import ExtractedDocument
from app.services import web_extractor


class RateLimited(Exception):
    """The host's rate limit is used up; the task should re-queue itself."""


class CrawlOutcome(StrEnum):
    EXTRACTED = "extracted"


async def _acquire(host: str) -> bool:
    """One hit on the per-host Redis limiter; True if allowed."""
    # Each task run has its own event loop (asyncio.run), and coredis only works inside
    # `async with` on the loop it was entered on, so the storage is built per call.
    strategy = FixedWindowRateLimiter(RedisStorage(settings.redis_url))
    async with strategy.storage.bridge.storage:
        return await strategy.hit(parse(settings.crawler_rate_limit), "crawler", host)


async def _wait_for_slot(url: str) -> None:
    host = (urlsplit(url).hostname or "").lower()
    if not await _acquire(host):
        raise RateLimited(host)


async def crawl_page(url: str) -> tuple[CrawlOutcome, ExtractedDocument | None]:
    """Rate limit -> extract. Raises RateLimited or ExtractionError."""
    # Celery tasks have no lifespan, so each run owns its client
    async with httpx.AsyncClient() as client:
        await _wait_for_slot(url)
        return CrawlOutcome.EXTRACTED, await web_extractor.extract_url(client, url)
