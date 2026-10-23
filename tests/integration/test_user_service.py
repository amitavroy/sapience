from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services import user as user_service


async def test_get_returns_user(db_session: AsyncSession):
    user = User(name="Ann", email="ann@example.com", password_hash="x")
    db_session.add(user)
    await db_session.commit()

    found = await user_service.get(db_session, user.id)

    assert found is not None
    assert found.email == "ann@example.com"


async def test_get_unknown_id_returns_none(db_session: AsyncSession):
    assert await user_service.get(db_session, 999) is None
