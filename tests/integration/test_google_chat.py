import json
from collections.abc import Callable

import httpx
import pytest

from app.core.config import settings
from app.services.google_chat import ACK, reply
from tests.google_chat_helpers import CHAT_FIXTURES, SLASH_FIXTURE, load_fixture

Sign = Callable[..., str]


def signed_event(name: str, token: str) -> dict:
    """A real captured event with its placeholder token swapped for a verifiable one."""
    event = load_fixture(name)
    event["authorizationEventObject"]["systemIdToken"] = token
    return event


@pytest.mark.parametrize("name", CHAT_FIXTURES)
async def test_valid_event_is_acked_and_queued(
    chat_client: httpx.AsyncClient, sign_google_token: Sign, dispatched: list[tuple], name: str
) -> None:
    token = sign_google_token()

    response = await chat_client.post("/ingest/google-chat", json=signed_event(name, token))

    assert response.status_code == 200
    assert response.json() == reply(ACK)
    assert dispatched == [
        (
            "app.tasks.google_chat.process_chat_event",
            load_fixture(name)["chat"],  # exactly as Google sent it, minus the token
            response.headers["x-request-id"],
        )
    ]
    assert token not in json.dumps(dispatched)  # the ID token never reaches the queue


async def test_slash_command_is_acked_and_queued(
    chat_client: httpx.AsyncClient, sign_google_token: Sign, dispatched: list[tuple]
) -> None:
    token = sign_google_token()

    response = await chat_client.post(
        "/ingest/google-chat", json=signed_event(SLASH_FIXTURE, token)
    )

    assert response.status_code == 200
    assert response.json() == reply(ACK)
    assert dispatched == [
        (
            "app.tasks.google_chat.process_chat_event",
            load_fixture(SLASH_FIXTURE)["chat"],
            response.headers["x-request-id"],
        )
    ]
    assert "appCommandPayload" in dispatched[0][1]
    assert token not in json.dumps(dispatched)


async def test_event_without_a_message_is_ignored(
    chat_client: httpx.AsyncClient, sign_google_token: Sign, dispatched: list[tuple]
) -> None:
    event = signed_event(CHAT_FIXTURES[0], sign_google_token())
    del event["chat"]["messagePayload"]  # e.g. the app was added to a space

    response = await chat_client.post("/ingest/google-chat", json=event)

    assert response.status_code == 200
    assert response.json() == {}
    assert dispatched == []


async def test_event_without_chat_is_ignored(
    chat_client: httpx.AsyncClient, sign_google_token: Sign, dispatched: list[tuple]
) -> None:
    event = signed_event(CHAT_FIXTURES[0], sign_google_token())
    del event["chat"]

    response = await chat_client.post("/ingest/google-chat", json=event)

    assert response.status_code == 200
    assert response.json() == {}
    assert dispatched == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda e: e.pop("authorizationEventObject"),
        lambda e: e["authorizationEventObject"].pop("systemIdToken"),
        lambda e: e["authorizationEventObject"].update(systemIdToken="not-a-jwt"),
    ],
    ids=["no-authorization-object", "no-token", "invalid-token"],
)
async def test_unverifiable_event_is_rejected(
    chat_client: httpx.AsyncClient, dispatched: list[tuple], mutate: Callable[[dict], object]
) -> None:
    event = load_fixture(CHAT_FIXTURES[0])
    mutate(event)

    response = await chat_client.post("/ingest/google-chat", json=event)

    assert response.status_code == 401
    assert dispatched == []


async def test_non_json_body_is_rejected(
    chat_client: httpx.AsyncClient, dispatched: list[tuple]
) -> None:
    response = await chat_client.post(
        "/ingest/google-chat", content="not json", headers={"content-type": "application/json"}
    )

    assert response.status_code == 401
    assert dispatched == []


async def test_token_for_another_audience_is_rejected(
    chat_client: httpx.AsyncClient, sign_google_token: Sign, dispatched: list[tuple]
) -> None:
    token = sign_google_token(aud="https://evil.example.test/ingest/google-chat")

    response = await chat_client.post(
        "/ingest/google-chat", json=signed_event(CHAT_FIXTURES[0], token)
    )

    assert response.status_code == 401
    assert dispatched == []


async def test_unconfigured_audience_rejects_everything(
    chat_client: httpx.AsyncClient,
    sign_google_token: Sign,
    dispatched: list[tuple],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "google_chat_audience", "")

    response = await chat_client.post(
        "/ingest/google-chat", json=signed_event(CHAT_FIXTURES[0], sign_google_token())
    )

    assert response.status_code == 401
    assert dispatched == []
