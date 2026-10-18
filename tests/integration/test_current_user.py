import httpx
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_token
from app.models.user import User

BODY = {"name": "Ann", "email": "ann@example.com", "password": "supersecret"}


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_valid_token_returns_user(client: httpx.AsyncClient):
    user = (await client.post("/auth/register", json=BODY)).json()
    r = await client.get("/user", headers=bearer(create_token(user["id"])))
    assert r.status_code == 200
    assert r.json() == user


async def test_no_token_401(client: httpx.AsyncClient):
    assert (await client.get("/user")).status_code == 401


async def test_garbage_token_401(client: httpx.AsyncClient):
    assert (await client.get("/user", headers=bearer("garbage"))).status_code == 401


async def test_expired_token_401(client: httpx.AsyncClient):
    user = (await client.post("/auth/register", json=BODY)).json()
    r = await client.get("/user", headers=bearer(create_token(user["id"], expires_minutes=-1)))
    assert r.status_code == 401


async def test_inactive_user_401(client: httpx.AsyncClient, db_session: AsyncSession):
    user = (await client.post("/auth/register", json=BODY)).json()
    await db_session.execute(update(User).values(is_active=False))
    await db_session.commit()
    assert (await client.get("/user", headers=bearer(create_token(user["id"])))).status_code == 401
