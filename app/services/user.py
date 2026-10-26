from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import dispatch
from app.core.config import settings
from app.core.logger import logger
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate
from app.tasks.user import welcome_user


class EmailTakenError(Exception):
    pass


async def get(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    return await db.scalar(select(User).where(User.email == email.lower()))


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    email = data.email.lower()
    if await get_by_email(db, email):
        raise EmailTakenError
    user = User(name=data.name, email=email, password_hash=await hash_password(data.password))
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as e:  # lost a race with a concurrent register
        await db.rollback()
        raise EmailTakenError from e
    await db.refresh(user)
    return user


async def register_user(db: AsyncSession, data: UserCreate) -> User:
    user = await create_user(db, data)
    await dispatch(welcome_user, user.id)
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_by_email(db, email)
    if (
        user is None
        or not user.is_active
        or user.password_hash is None  # created from Chat; it has no password to log in with
        or not await verify_password(password, user.password_hash)
    ):
        return None
    return user


async def resolve_chat_user(
    db: AsyncSession, chat_user_id: str, email: str | None, display_name: str
) -> int | None:
    """The app user behind a Chat sender: linked by Chat id, else by email once, else created.

    `email` must come from the verified event. None = the sender may not use the bot.
    """
    user = await _by_chat_id(db, chat_user_id)
    if user is None and email and _domain_allowed(email):
        user = await get_by_email(db, email)
        if user is not None and user.google_chat_user_id not in (None, chat_user_id):
            logger.warning(
                f"chat sender email already linked to another chat user user_id={user.id}"
            )
            return None
        action = "linked" if user is not None else "created"
        try:
            if user is None:
                user = User(name=display_name, email=email.lower(), password_hash=None)
                db.add(user)
            user.google_chat_user_id = chat_user_id
            await db.commit()
        except IntegrityError:  # a concurrent first message linked or created it
            await db.rollback()
            user = await _by_chat_id(db, chat_user_id)
        else:
            logger.info(f"chat sender {action} user_id={user.id} chat_user={chat_user_id}")
    # the domain is checked on every event, so narrowing the setting cuts off linked users too
    if user is None or not user.is_active or not _domain_allowed(user.email):
        return None
    return user.id


async def _by_chat_id(db: AsyncSession, chat_user_id: str) -> User | None:
    return await db.scalar(select(User).where(User.google_chat_user_id == chat_user_id))


def _domain_allowed(email: str) -> bool:
    # exact match on the part after the last "@"; empty setting = nobody
    return email.rpartition("@")[2].lower() in settings.chat_allowed_email_domains
