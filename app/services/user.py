from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import dispatch
from app.core.security import hash_password, verify_password
from app.db.session import task_session
from app.models.user import User
from app.schemas.user import UserCreate
from app.tasks.user import welcome_user


class EmailTakenError(Exception):
    pass


async def get(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)


async def get_for_task(user_id: int) -> User | None:
    """For Celery tasks, which have no request-scoped session."""
    async with task_session() as db:
        return await get(db, user_id)


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
        or not await verify_password(password, user.password_hash)
    ):
        return None
    return user
