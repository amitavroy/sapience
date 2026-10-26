import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.models.user import User

BODY = {"name": "Ann", "email": "ann@example.com", "password": "supersecret"}


async def login(client: httpx.AsyncClient, email: str, password: str) -> httpx.Response:
    return await client.post("/auth/login", json={"email": email, "password": password})


async def test_login_ok(client: httpx.AsyncClient):
    user = (await client.post("/auth/register", json=BODY)).json()
    r = await login(client, BODY["email"], BODY["password"])
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert decode_token(r.json()["access_token"]) == user["id"]


async def test_inactive_user_401(client: httpx.AsyncClient, db_session: AsyncSession):
    await client.post("/auth/register", json=BODY)
    await db_session.execute(update(User).values(is_active=False))
    await db_session.commit()
    assert (await login(client, BODY["email"], BODY["password"])).status_code == 401


@pytest.mark.parametrize(
    ("email", "password"),
    [("ann@example.com", "wrongpassword"), ("who@example.com", "supersecret")],
)
async def test_bad_credentials_401(client: httpx.AsyncClient, email: str, password: str):
    await client.post("/auth/register", json=BODY)
    r = await login(client, email, password)
    assert r.status_code == 401
    assert r.json()["detail"] == "Incorrect email or password"


async def test_user_created_from_chat_cannot_log_in(
    client: httpx.AsyncClient, db_session: AsyncSession
):
    db_session.add(User(name="Ann", email="ann@example.com", password_hash=None))
    await db_session.commit()

    for password in ("", "anything"):
        assert (await login(client, "ann@example.com", password)).status_code == 401
