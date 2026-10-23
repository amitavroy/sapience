import json
from collections.abc import Iterator
from urllib.parse import parse_qs

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.google_chat_client import GoogleChatClient, get_google_chat_client
from app.core.logger import logger
from app.core.security import create_token
from app.main import app
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


BODY = {"space": "spaces/AAA", "text": "hi"}


@pytest.fixture
def log_records() -> Iterator[list[dict]]:
    records: list[dict] = []
    sink = logger.add(lambda m: records.append(m.record), level="DEBUG")
    yield records
    logger.remove(sink)


async def test_not_configured_503(
    client: httpx.AsyncClient, chat_api: ChatApiServer, auth: dict[str, str]
):
    async with httpx.AsyncClient(transport=chat_api.transport) as http:
        unconfigured = GoogleChatClient(http, "")
        app.dependency_overrides[get_google_chat_client] = lambda: unconfigured
        r = await client.post(URL, json=BODY, headers=auth)

    assert r.status_code == 503
    assert r.json() == {"detail": "Google Chat sending is not configured"}
    assert chat_api.requests == []


@pytest.mark.parametrize("status", [403, 404])
async def test_chat_rejection_502_without_secrets_in_logs(
    client: httpx.AsyncClient,
    google_chat_client: GoogleChatClient,
    chat_api: ChatApiServer,
    auth: dict[str, str],
    log_records: list[dict],
    status: int,
):
    chat_api.chat_status = status

    r = await client.post(URL, json=BODY, headers=auth)

    assert r.status_code == 502
    assert r.json() == {"detail": f"Google Chat rejected the message ({status})"}
    logged = " ".join(rec["message"] for rec in log_records)
    assert f"chat said {status}" in logged
    for secret in ("Bearer", "assertion", "PRIVATE KEY", CHAT_TOKEN):
        assert secret not in logged


async def test_token_endpoint_rejection_502(
    client: httpx.AsyncClient,
    google_chat_client: GoogleChatClient,
    chat_api: ChatApiServer,
    auth: dict[str, str],
):
    chat_api.token_status = 400

    r = await client.post(URL, json=BODY, headers=auth)

    assert r.status_code == 502
    assert r.json() == {"detail": "Google Chat rejected the message (400)"}
    assert chat_api.chat_requests == []


async def test_timeout_502_without_status(
    client: httpx.AsyncClient,
    google_chat_client: GoogleChatClient,
    chat_api: ChatApiServer,
    auth: dict[str, str],
):
    chat_api.chat_error = httpx.ConnectTimeout("slow")

    r = await client.post(URL, json=BODY, headers=auth)

    assert r.status_code == 502
    assert r.json() == {"detail": "Google Chat rejected the message (None)"}
