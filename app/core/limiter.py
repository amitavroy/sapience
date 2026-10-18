from fastapi import HTTPException, Request
from limits import parse
from limits.aio.storage import RedisStorage
from limits.aio.strategies import FixedWindowRateLimiter

from app.core.config import settings
from app.core.logger import logger

# limits.aio (not slowapi): slowapi's storage is sync and would block the event loop.
strategy = FixedWindowRateLimiter(RedisStorage(settings.redis_url))
# coredis only works inside `async with redis:`; the app lifespan enters it.
redis = strategy.storage.bridge.storage
rate = parse(settings.rate_limit)


async def rate_limit(request: Request) -> None:
    key = request.client.host if request.client else "unknown"
    try:
        allowed = await strategy.hit(rate, key)
    except Exception:
        logger.exception("rate limiter backend unavailable")
        raise HTTPException(status_code=503, detail="Rate limiter unavailable") from None
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many requests")
