import httpx
import pytest

BODY = {"name": "Ann", "email": "Ann@Example.com", "password": "supersecret"}


async def test_register_ok(client: httpx.AsyncClient):
    r = await client.post("/auth/register", json=BODY)
    assert r.status_code == 201
    assert r.json()["email"] == "ann@example.com"


async def test_duplicate_email_409(client: httpx.AsyncClient):
    await client.post("/auth/register", json=BODY)
    r = await client.post("/auth/register", json={**BODY, "email": "ann@example.com"})
    assert r.status_code == 409


@pytest.mark.parametrize("bad", [{"email": "nope"}, {"password": "short"}])
async def test_invalid_input_422(client: httpx.AsyncClient, bad: dict):
    r = await client.post("/auth/register", json={**BODY, **bad})
    assert r.status_code == 422


async def test_hash_not_exposed(client: httpx.AsyncClient):
    r = await client.post("/auth/register", json=BODY)
    assert "password" not in r.text
