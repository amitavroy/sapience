import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Literal
from uuid import uuid4

from coredis import PureToken, Redis
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings
from app.core.logger import logger

LOCK_TTL = 900  # seconds; also the backstop that frees the lock after a crashed worker
SEEN_TTL = 86400  # Celery is at-least-once and Google retries events, so remember a day

# Every lock operation compares the token first: after our lock expires, another drain may
# hold it, and we must neither remove it, extend it, nor pop the item it is now working on.
_RELEASE = (
    "if redis.call('get', KEYS[1]) == ARGV[1] "
    "then return redis.call('del', KEYS[1]) else return 0 end"
)
_REFRESH = (
    "if redis.call('get', KEYS[1]) == ARGV[1] "
    "then return redis.call('expire', KEYS[1], ARGV[2]) else return 0 end"
)
_POP = (
    "if redis.call('get', KEYS[1]) == ARGV[1] "
    "then redis.call('lpop', KEYS[2]) return 1 else return 0 end"
)


class QueueItem(BaseModel):
    kind: Literal["message", "reset"] = "message"
    space: str
    user: str
    message_name: str = ""
    text: str = ""
    display_name: str = ""
    # from the Google-authenticated event, never the message text; matches the app user
    email: str | None = None
    trace_id: str = ""
    enqueued_at: float = Field(default_factory=time.time)


@asynccontextmanager
async def open_redis() -> AsyncIterator[Redis]:
    # coredis only works inside `async with` on the loop it was entered on, and every Celery
    # task has its own loop, so the client is opened per use
    async with Redis.from_url(settings.redis_url) as redis:
        yield redis


def queue_key(space: str, user: str) -> str:
    return f"chat:q:{space}:{user}"


def lock_key(space: str, user: str) -> str:
    return f"chat:lock:{space}:{user}"


def seen_key(message_name: str) -> str:
    return f"chat:seen:{message_name}"


async def enqueue(redis: Redis, item: QueueItem) -> bool:
    """False if this Chat message was already queued (dedup)."""
    if item.message_name and not await redis.set(
        seen_key(item.message_name), "1", condition=PureToken.NX, ex=SEEN_TTL
    ):
        return False
    try:
        await redis.rpush(queue_key(item.space, item.user), [item.model_dump_json()])
    except Exception:
        # without this a retry of the same event would be dropped as a duplicate
        if item.message_name:
            try:
                await redis.delete([seen_key(item.message_name)])
            except Exception as e:
                logger.warning(f"could not clear the dedup key: {type(e).__name__}")
        raise
    return True


async def release(redis: Redis, key: str, token: str) -> None:
    await redis.eval(_RELEASE, [key], [token])


async def drain(
    redis: Redis, space: str, user: str, process: Callable[[QueueItem], Awaitable[None]]
) -> None:
    """Run the conversation's queued items in order, one drain per conversation at a time.

    `process` must not raise: it handles its own failures, so an item always leaves the queue.
    """
    queue, lock = queue_key(space, user), lock_key(space, user)
    while True:
        token = uuid4().hex
        if not await redis.set(lock, token, condition=PureToken.NX, ex=LOCK_TTL):
            logger.info(f"conversation busy, its drain will pick this up space={space}")
            return  # another drain owns this conversation and will reach the item
        try:
            # peek, process, then pop: a crashed worker leaves the item for the next drain
            while (raw := await redis.lindex(queue, 0)) is not None:
                if not await redis.eval(_REFRESH, [lock], [token, LOCK_TTL]):
                    logger.warning(f"conversation lock lost, stopping drain space={space}")
                    break  # not return: the llen recheck below must still run
                try:
                    item = QueueItem.model_validate_json(raw)
                except ValidationError as e:
                    # e.g. a schema change between deploys; never leave it blocking the head
                    logger.error(
                        f"dropping unreadable queue item space={space}: {e.error_count()} errors"
                    )
                    await redis.eval(_POP, [lock, queue], [token])
                    continue
                await process(item)
                if not await redis.eval(_POP, [lock, queue], [token]):
                    # if nobody took the lock over, the next pass redoes this item (at-least-once)
                    logger.warning(f"conversation lock lost mid-item, stopping space={space}")
                    break
        finally:
            await release(redis, lock, token)
        # an item pushed between the last pop and the release would be stranded
        if not await redis.llen(queue):
            return
