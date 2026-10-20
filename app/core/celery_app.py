import asyncio
from typing import Any

from celery import Celery, Task

from app.core.config import settings

celery_app = Celery(
    "app",
    broker=settings.celery_broker_url,
    include=["app.tasks.user", "app.tasks.google_chat", "app.tasks.crawler"],
)
celery_app.conf.update(
    task_ignore_result=True,  # nothing reads results yet
    task_acks_late=True,  # at-least-once: tasks must be idempotent
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)


async def dispatch(task: Task, *args: Any) -> None:
    """Enqueue a task without blocking the event loop."""
    # SYNC-EXCEPTION: Celery's publish is blocking Redis I/O; to_thread keeps it off the loop
    await asyncio.to_thread(task.delay, *args)
