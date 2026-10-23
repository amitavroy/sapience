import asyncio

from app.core.celery_app import celery_app
from app.core.logger import logger
from app.db.session import task_session
from app.models.user import User


async def _get_user(user_id: int) -> User | None:
    from app.services import user as user_service  # local: services.user imports this module

    async with task_session() as db:
        return await user_service.get(db, user_id)


@celery_app.task
def welcome_user(user_id: int) -> None:
    # SYNC-EXCEPTION: Celery task bodies are sync; asyncio.run drives the async work
    user = asyncio.run(_get_user(user_id))
    if user is None:  # deleted before the job ran; nothing to do
        logger.warning(f"welcome_user: user {user_id} not found")
        return
    logger.info(f"welcome {user.email}")  # stub: send the welcome mail here
