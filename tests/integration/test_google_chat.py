import json
from collections.abc import Callable

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.services import user as user_service
from app.services.google_chat import ACK, NO_ACCESS_REPLY, reply
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


async def test_first_mention_creates_the_sender_as_a_user(
    chat_client: httpx.AsyncClient,
    sign_google_token: Sign,
    dispatched: list[tuple],
    db_session: AsyncSession,
) -> None:
    response = await chat_client.post(
        "/ingest/google-chat", json=signed_event(CHAT_FIXTURES[0], sign_google_token())
    )

    assert response.json() == reply(ACK)
    user = await user_service.get_by_email(db_session, "ann@example.com")
    assert (user.google_chat_user_id, user.password_hash) == ("users/1001", None)
    assert len(dispatched) == 1


@pytest.mark.parametrize("name", [CHAT_FIXTURES[0], SLASH_FIXTURE])
@pytest.mark.parametrize(
    "reject",
    [
        lambda e, m: m.setattr(settings, "google_chat_allowed_email_domains", "example.org"),
        lambda e, m: m.setattr(settings, "google_chat_allowed_email_domains", ""),
        lambda e, m: e["chat"]["user"].pop("email"),
    ],
    ids=["outside-domains", "no-domains", "no-email-not-linked"],
)
async def test_rejected_sender_gets_no_access_and_nothing_is_queued(
    chat_client: httpx.AsyncClient,
    sign_google_token: Sign,
    dispatched: list[tuple],
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    reject: Callable,
) -> None:
    event = signed_event(name, sign_google_token())
    reject(event, monkeypatch)

    response = await chat_client.post("/ingest/google-chat", json=event)

    assert response.status_code == 200
    assert response.json() == reply(NO_ACCESS_REPLY)
    assert dispatched == []
    assert await db_session.scalar(select(func.count()).select_from(User)) == 0


async def test_inactive_sender_gets_no_access(
    chat_client: httpx.AsyncClient,
    sign_google_token: Sign,
    dispatched: list[tuple],
    db_session: AsyncSession,
) -> None:
    db_session.add(
        User(
            name="Ann",
            email="ann@example.com",
            password_hash="x",
            google_chat_user_id="users/1001",
            is_active=False,
        )
    )
    await db_session.commit()

    response = await chat_client.post(
        "/ingest/google-chat", json=signed_event(CHAT_FIXTURES[0], sign_google_token())
    )

    assert response.json() == reply(NO_ACCESS_REPLY)
    assert dispatched == []


async def test_event_with_nothing_to_queue_does_no_lookup(
    chat_client: httpx.AsyncClient,
    sign_google_token: Sign,
    dispatched: list[tuple],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def no_lookup(*args) -> None:
        raise AssertionError("sender resolved for an event with nothing to queue")

    monkeypatch.setattr(user_service, "resolve_chat_user", no_lookup)
    event = signed_event(CHAT_FIXTURES[0], sign_google_token())
    del event["chat"]["messagePayload"]

    response = await chat_client.post("/ingest/google-chat", json=event)

    assert response.json() == {}
    assert dispatched == []
