import time
from enum import StrEnum
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from limits import parse
from limits.aio.storage import RedisStorage
from limits.aio.strategies import FixedWindowRateLimiter

from app.core.config import settings
from app.core.logger import logger
from app.schemas.extracted_document import ExtractedDocument
from app.services import web_extractor


class RateLimited(Exception):
    """The host's rate limit is used up; the task should re-queue itself."""


class CrawlOutcome(StrEnum):
    EXTRACTED = "extracted"
    ROBOTS_DISALLOWED = "robots_disallowed"


# origin -> (expires_at, parsed robots.txt); lives for the worker process
_robots_cache: dict[str, tuple[float, RobotFileParser]] = {}


async def _acquire(host: str) -> bool:
    """One hit on the per-host Redis limiter; True if allowed."""
    # Each task run has its own event loop (asyncio.run), and coredis only works inside
    # `async with` on the loop it was entered on, so the storage is built per call.
    strategy = FixedWindowRateLimiter(RedisStorage(settings.redis_url))
    async with strategy.storage.bridge.storage:
        return await strategy.hit(parse(settings.crawler_rate_limit), "crawler", host)


async def _wait_for_slot(host: str) -> None:
    if not await _acquire(host):
        raise RateLimited(host)


async def _fetch_robots(client: httpx.AsyncClient, origin: str, host: str) -> RobotFileParser:
    """RFC 9309: 4xx = everything allowed, 5xx or network error = everything disallowed."""
    parser = RobotFileParser()
    await _wait_for_slot(host)  # the robots.txt request counts against the host's limit
    try:
        response = await client.get(
            f"{origin}/robots.txt",
            headers={"User-Agent": settings.crawler_user_agent},
            timeout=settings.crawler_timeout_seconds,
            follow_redirects=True,
        )
    except httpx.TransportError as exc:
        logger.warning("robots.txt unreachable for {} ({}): treating as disallowed", host, exc)
        parser.disallow_all = True
        return parser
    if response.status_code >= 500:
        logger.warning(
            "robots.txt for {} returned {}: treating as disallowed", host, response.status_code
        )
        parser.disallow_all = True
    elif response.status_code >= 400:
        parser.allow_all = True
    else:
        parser.parse(response.text.splitlines())
    return parser


async def _robots_allows(client: httpx.AsyncClient, url: str) -> bool:
    """RFC 9309 semantics, `*` group only; parsed robots.txt cached per host in-process."""
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc.lower()}"
    cached = _robots_cache.get(origin)
    if cached is None or cached[0] <= time.monotonic():
        parser = await _fetch_robots(client, origin, (parts.hostname or "").lower())
        expires_at = time.monotonic() + settings.crawler_robots_cache_seconds
        cached = _robots_cache[origin] = (expires_at, parser)
    return cached[1].can_fetch("*", url)


async def crawl_page(url: str) -> tuple[CrawlOutcome, ExtractedDocument | None]:
    """robots.txt -> rate limit -> extract. Raises RateLimited or ExtractionError."""
    host = (urlsplit(url).hostname or "").lower()
    # Celery tasks have no lifespan, so each run owns its client
    async with httpx.AsyncClient() as client:
        if not await _robots_allows(client, url):
            return CrawlOutcome.ROBOTS_DISALLOWED, None
        await _wait_for_slot(host)
        return CrawlOutcome.EXTRACTED, await web_extractor.extract_url(client, url)
