import time
from collections.abc import Awaitable, Callable
from typing import Literal
from uuid import uuid4

from coredis import PureToken, Redis
from pydantic import BaseModel, Field

from app.core.logger import logger

LOCK_TTL = 900  # seconds; also the backstop that frees the lock after a crashed worker
SEEN_TTL = 86400  # Celery is at-least-once and Google retries events, so remember a day

# compare-and-delete: never remove a lock another worker took after ours expired
_RELEASE = (
    "if redis.call('get', KEYS[1]) == ARGV[1] "
    "then return redis.call('del', KEYS[1]) else return 0 end"
)


class QueueItem(BaseModel):
    kind: Literal["message", "reset"] = "message"
    space: str
    user: str
    message_name: str = ""
    text: str = ""
    display_name: str = ""
    trace_id: str = ""
    enqueued_at: float = Field(default_factory=time.time)


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
    await redis.rpush(queue_key(item.space, item.user), [item.model_dump_json()])
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
                await redis.expire(lock, LOCK_TTL)
                await process(QueueItem.model_validate_json(raw))
                await redis.lpop(queue)
        finally:
            await release(redis, lock, token)
        # an item pushed between the last pop and the release would be stranded
        if not await redis.llen(queue):
            return
