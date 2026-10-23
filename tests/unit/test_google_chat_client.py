import asyncio
import time
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.google_chat_client import (
    GoogleChatClient,
    GoogleChatError,
    GoogleChatNotConfiguredError,
)
from tests.google_chat_helpers import ChatApiServer, write_service_account_file


@pytest.fixture
def credentials_file(rsa_key: rsa.RSAPrivateKey, tmp_path: Path) -> str:
    return write_service_account_file(tmp_path / "sa.json", rsa_key)


@pytest.fixture
async def http(chat_api: ChatApiServer) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(transport=chat_api.transport) as http:
        yield http


@pytest.fixture
def chat(http: httpx.AsyncClient, credentials_file: str) -> GoogleChatClient:
    return GoogleChatClient(http, credentials_file)


async def test_two_sends_mint_one_token(chat: GoogleChatClient, chat_api: ChatApiServer):
    await chat.create_message("spaces/AAA", "one")
    await chat.create_message("spaces/AAA", "two")

    assert len(chat_api.token_requests) == 1
    assert len(chat_api.chat_requests) == 2


async def test_expired_token_is_minted_again(
    chat: GoogleChatClient, chat_api: ChatApiServer, monkeypatch: pytest.MonkeyPatch
):
    now = time.monotonic()
    clock = SimpleNamespace(now=now)
    monkeypatch.setattr(
        "app.core.google_chat_client.time",
        SimpleNamespace(monotonic=lambda: clock.now, time=time.time),
    )

    await chat.create_message("spaces/AAA", "one")
    clock.now += 3600  # past expires_in minus the refresh margin
    await chat.create_message("spaces/AAA", "two")

    assert len(chat_api.token_requests) == 2


async def test_concurrent_sends_mint_one_token(chat: GoogleChatClient, chat_api: ChatApiServer):
    await asyncio.gather(
        chat.create_message("spaces/AAA", "one"), chat.create_message("spaces/AAA", "two")
    )

    assert len(chat_api.token_requests) == 1
    assert len(chat_api.chat_requests) == 2


async def test_401_mints_again_and_retries_once(chat: GoogleChatClient, chat_api: ChatApiServer):
    chat_api.chat_statuses = [401, 200]

    name = await chat.create_message("spaces/AAA", "hi")

    assert name == "spaces/AAA/messages/M1"
    assert len(chat_api.token_requests) == 2
    assert len(chat_api.chat_requests) == 2


async def test_second_401_is_an_error(chat: GoogleChatClient, chat_api: ChatApiServer):
    chat_api.chat_statuses = [401, 401]

    with pytest.raises(GoogleChatError) as exc:
        await chat.create_message("spaces/AAA", "hi")

    assert exc.value.status == 401
    assert len(chat_api.chat_requests) == 2


async def test_chat_error_carries_status_and_googles_message(
    chat: GoogleChatClient, chat_api: ChatApiServer
):
    chat_api.chat_status = 403

    with pytest.raises(GoogleChatError) as exc:
        await chat.create_message("spaces/AAA", "hi")

    assert exc.value.status == 403
    assert str(exc.value) == "chat said 403"


async def test_token_endpoint_rejection_is_an_error(
    chat: GoogleChatClient, chat_api: ChatApiServer
):
    chat_api.token_status = 400

    with pytest.raises(GoogleChatError) as exc:
        await chat.create_message("spaces/AAA", "hi")

    assert exc.value.status == 400
    assert chat_api.chat_requests == []


async def test_network_error_has_no_status(chat: GoogleChatClient, chat_api: ChatApiServer):
    chat_api.chat_error = httpx.ConnectTimeout("slow")

    with pytest.raises(GoogleChatError) as exc:
        await chat.create_message("spaces/AAA", "hi")

    assert exc.value.status is None


async def test_empty_credentials_path_not_configured(
    http: httpx.AsyncClient, chat_api: ChatApiServer
):
    with pytest.raises(GoogleChatNotConfiguredError):
        await GoogleChatClient(http, "").create_message("spaces/AAA", "hi")

    assert chat_api.requests == []


async def test_missing_credentials_file_not_configured(
    http: httpx.AsyncClient, chat_api: ChatApiServer, tmp_path: Path
):
    with pytest.raises(GoogleChatNotConfiguredError):
        await GoogleChatClient(http, str(tmp_path / "nope.json")).create_message("spaces/A", "x")

    assert chat_api.requests == []


async def test_credentials_without_private_key_not_configured(
    http: httpx.AsyncClient, chat_api: ChatApiServer, tmp_path: Path
):
    path = tmp_path / "sa.json"
    path.write_text('{"client_email": "a@b.c", "private_key_id": "k", "token_uri": "https://t"}')

    with pytest.raises(GoogleChatNotConfiguredError) as exc:
        await GoogleChatClient(http, str(path)).create_message("spaces/AAA", "hi")

    assert str(exc.value) == "unreadable credentials file: KeyError"
    assert chat_api.requests == []
