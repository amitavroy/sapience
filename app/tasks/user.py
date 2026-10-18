import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.logger import logger
from app.db.session import task_session
from app.models.user import User


async def _welcome_user(db: AsyncSession, user_id: int) -> None:
    user = await db.get(User, user_id)
    if user is None:  # deleted before the job ran; nothing to do
        logger.warning(f"welcome_user: user {user_id} not found")
        return
    logger.info(f"welcome {user.email}")  # stub: send the welcome mail here


@celery_app.task
def welcome_user(user_id: int) -> None:
    # SYNC-EXCEPTION: Celery task bodies are sync; asyncio.run drives the async work
    async def run() -> None:
        async with task_session() as db:
            await _welcome_user(db, user_id)

    asyncio.run(run())
