import os
import time
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from types import SimpleNamespace

import httpx
import jwt
import pytest
from celery import Celery
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")  # never connected
os.environ.setdefault("LOG_FILE_LEVEL", "")  # tests never write to logs/
os.environ["CELERY_BROKER_URL"] = "redis://127.0.0.1:1/0"  # dead on purpose; never the .env broker

from app.core.config import settings  # noqa: E402
from app.core.deps import get_db  # noqa: E402
from app.core.google_auth import GoogleTokenVerifier, get_google_verifier  # noqa: E402
from app.core.google_chat_client import GoogleChatClient, get_google_chat_client  # noqa: E402
from app.core.limiter import rate_limit  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.main import app  # noqa: E402
from tests.google_chat_helpers import (  # noqa: E402
    GOOGLE_AUDIENCE,
    GOOGLE_EMAIL,
    GOOGLE_KID,
    ChatApiServer,
    JwksServer,
    new_rsa_key,
    public_jwk,
    write_service_account_file,
)


@pytest.fixture(autouse=True)
def no_celery_publish(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any test that publishes a task instead of stubbing it, with or without Redis."""

    def refuse(self, name, *args, **kwargs):
        raise AssertionError(f"test published Celery task {name!r}: stub .delay or dispatch")

    monkeypatch.setattr(Celery, "send_task", refuse)


@pytest.fixture(autouse=True)
def dispatched(monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """Record task dispatches instead of publishing to a broker (none in tests)."""
    calls: list[tuple] = []

    async def fake_dispatch(task, *args) -> None:
        calls.append((task.name, *args))

    monkeypatch.setattr("app.services.user.dispatch", fake_dispatch)
    monkeypatch.setattr("app.routers.ingest.dispatch", fake_dispatch)
    return calls


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fks(dbapi_conn, _record) -> None:
        # SQLite ignores FKs (and so ON DELETE CASCADE / SET NULL) unless turned on per connection
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[rate_limit] = lambda: None  # limiter off; no Redis in tests
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# --- Google Chat webhook: no network, tokens signed with a throwaway RSA key ---


@pytest.fixture(scope="session")
def rsa_key() -> rsa.RSAPrivateKey:
    return new_rsa_key()


@pytest.fixture
def jwks(rsa_key: rsa.RSAPrivateKey) -> JwksServer:
    return JwksServer([[public_jwk(rsa_key)]])


@pytest.fixture
async def google_verifier(jwks: JwksServer) -> AsyncIterator[GoogleTokenVerifier]:
    async with httpx.AsyncClient(transport=jwks.transport) as http:
        yield GoogleTokenVerifier(http)


@pytest.fixture
def google_settings(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    monkeypatch.setattr(settings, "google_chat_audience", GOOGLE_AUDIENCE)
    monkeypatch.setattr(settings, "google_chat_service_account_email", GOOGLE_EMAIL)
    return SimpleNamespace(audience=GOOGLE_AUDIENCE, email=GOOGLE_EMAIL)


@pytest.fixture
def sign_google_token(rsa_key: rsa.RSAPrivateKey) -> Callable[..., str]:
    def sign(
        *, key: rsa.RSAPrivateKey | None = None, kid: str | None = GOOGLE_KID, **overrides
    ) -> str:
        """Valid claims by default; a claim override of None removes that claim."""
        now = int(time.time())
        claims = {
            "aud": GOOGLE_AUDIENCE,
            "azp": "1234567890",
            "email": GOOGLE_EMAIL,
            "email_verified": True,
            "exp": now + 3600,
            "iat": now,
            "iss": "https://accounts.google.com",
            "sub": "1234567890",
            **overrides,
        }
        claims = {k: v for k, v in claims.items() if v is not None}
        headers = {"kid": kid} if kid else {}
        return jwt.encode(claims, key or rsa_key, algorithm="RS256", headers=headers)

    return sign


@pytest.fixture
def chat_client(
    client: httpx.AsyncClient,
    google_verifier: GoogleTokenVerifier,
    google_settings: SimpleNamespace,
) -> httpx.AsyncClient:
    """`client` whose Google verifier is backed by the fake certs endpoint.

    The lifespan does not run under ASGITransport, so app.state has no verifier; this override
    is required. `client` clears dependency_overrides on teardown.
    """
    app.dependency_overrides[get_google_verifier] = lambda: google_verifier
    return client


# --- Google Chat outbound: fake token endpoint + Chat API, real signing key in a temp file ---


@pytest.fixture
def chat_api() -> ChatApiServer:
    return ChatApiServer()


@pytest.fixture
async def google_chat_client(
    client: httpx.AsyncClient,
    chat_api: ChatApiServer,
    rsa_key: rsa.RSAPrivateKey,
    tmp_path: Path,
) -> AsyncIterator[GoogleChatClient]:
    """A real GoogleChatClient on the fake transport, wired in as the endpoint's dependency.

    `client` clears dependency_overrides on teardown.
    """
    credentials_file = write_service_account_file(tmp_path / "sa.json", rsa_key)
    async with httpx.AsyncClient(transport=chat_api.transport) as http:
        chat = GoogleChatClient(http, credentials_file)
        app.dependency_overrides[get_google_chat_client] = lambda: chat
        yield chat
