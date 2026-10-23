import json
from urllib.parse import parse_qs

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.google_chat_client import GoogleChatClient
from app.core.security import create_token
from tests.google_chat_helpers import (
    CHAT_TOKEN,
    SA_EMAIL,
    SA_KEY_ID,
    TOKEN_URI,
    ChatApiServer,
)

USER = {"name": "Ann", "email": "ann@example.com", "password": "supersecret"}
URL = "/google-chat/messages"


@pytest.fixture
async def auth(client: httpx.AsyncClient) -> dict[str, str]:
    user = (await client.post("/auth/register", json=USER)).json()
    return {"Authorization": f"Bearer {create_token(user['id'])}"}


async def test_posts_message_to_space(
    client: httpx.AsyncClient,
    google_chat_client: GoogleChatClient,
    chat_api: ChatApiServer,
    rsa_key: rsa.RSAPrivateKey,
    auth: dict[str, str],
):
    r = await client.post(URL, json={"space": "spaces/AAA", "text": "hi"}, headers=auth)

    assert r.status_code == 200
    assert r.json() == {"name": "spaces/AAA/messages/M1"}

    [token_req] = chat_api.token_requests
    form = parse_qs(token_req.content.decode())
    assert form["grant_type"] == ["urn:ietf:params:oauth:grant-type:jwt-bearer"]
    assertion = form["assertion"][0]
    assert jwt.get_unverified_header(assertion)["kid"] == SA_KEY_ID
    claims = jwt.decode(assertion, rsa_key.public_key(), algorithms=["RS256"], audience=TOKEN_URI)
    assert claims["iss"] == SA_EMAIL
    assert claims["scope"] == "https://www.googleapis.com/auth/chat.bot"

    [chat_req] = chat_api.chat_requests
    assert chat_req.method == "POST"
    assert chat_req.url.path == "/v1/spaces/AAA/messages"
    assert chat_req.headers["authorization"] == f"Bearer {CHAT_TOKEN}"
    assert json.loads(chat_req.content) == {"text": "hi"}


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer garbage"}])
async def test_requires_login(
    client: httpx.AsyncClient,
    google_chat_client: GoogleChatClient,
    chat_api: ChatApiServer,
    headers: dict[str, str],
):
    r = await client.post(URL, json={"space": "spaces/AAA", "text": "hi"}, headers=headers)
    assert r.status_code == 401
    assert chat_api.requests == []


@pytest.mark.parametrize(
    "body",
    [
        {"space": "AAA", "text": "hi"},
        {"space": "spaces/a/../b", "text": "hi"},
        {"space": "spaces/", "text": "hi"},
        {"space": "spaces/AAA", "text": ""},
        {"space": "spaces/AAA", "text": "   "},
        {"space": "spaces/AAA", "text": "x" * 4001},
    ],
)
async def test_invalid_body_422(
    client: httpx.AsyncClient,
    google_chat_client: GoogleChatClient,
    chat_api: ChatApiServer,
    auth: dict[str, str],
    body: dict,
):
    r = await client.post(URL, json=body, headers=auth)
    assert r.status_code == 422
    assert chat_api.requests == []
