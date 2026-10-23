# Send Google Chat messages to a space via the Chat API (GH-6)

## To-do

Each slice ends in a working, reviewable state with passing tests. Pause for review after each slice.

| # | Slice | Step | Done |
|---|-------|------|------|
| 1 | Post a message end-to-end | GCP: create a service account in the Chat app's project, download its JSON key into git-ignored `secrets/` (see Setup) | [x] |
| 1 | Post a message end-to-end | `app/core/config.py` + `.env.example`: `GOOGLE_CHAT_CREDENTIALS_FILE` (empty default); `.gitignore`: `secrets/` | [x] |
| 1 | Post a message end-to-end | `app/core/google_chat_client.py`: `ServiceAccountCredentials.from_file`, `GoogleChatClient` with token minting (JWT-bearer grant) and `create_message(space, text) -> str` | [x] |
| 1 | Post a message end-to-end | `app/main.py` lifespan: `app.state.google_chat_client` on the shared httpx client; `get_google_chat_client` dependency | [x] |
| 1 | Post a message end-to-end | `app/schemas/google_chat.py`: `SendMessageRequest`, `SendMessageResponse`; `app/services/google_chat.py`: `send_message` | [x] |
| 1 | Post a message end-to-end | `app/routers/google_chat.py`: `POST /google-chat/messages` behind `CurrentUser`; register in `main.py` | [x] |
| 1 | Post a message end-to-end | `docs/bruno/send-chat-message.bru` | [x] |
| 1 | Post a message end-to-end | Tests: happy path through the endpoint with `MockTransport` (token call + create call, correct URL, body, bearer); 401 without a JWT; 422 for a bad `space` / empty or too-long `text` | [x] |
| 1 | Post a message end-to-end | Manual: post via Bruno to a space the app is in; message appears in the space as the app | [x] |
| 2 | Token reuse and failures | Token cached until 60 s before expiry, one mint under concurrent calls (`asyncio.Lock`); a 401 from Chat drops the token and retries once | [x] |
| 2 | Token reuse and failures | `GoogleChatNotConfiguredError` → 503; Google 4xx/5xx or network error → `GoogleChatError` → 502 with Google's status; never log the token or key | [x] |
| 2 | Token reuse and failures | Tests: two sends mint one token; expired token re-mints; 401 → re-mint + retry once, second 401 → 502; empty setting / missing file / bad JSON → 503; Chat 403/404 → 502; token endpoint 400 → 502 | [x] |
| 3 | Docs | `docs/wiki/google-bot.md`: "Sending messages" section (setup, env var, endpoint, troubleshooting); one line in `docs/wiki/index.md` | [x] |

## Context

The Google Chat app (GH-2, GH-1, plans 005/006) only **receives** events. `POST /ingest/google-chat` verifies Google's ID token, queues the event, and answers synchronously with the "Got it" add-on reply. That synchronous reply is the only thing the bot can ever say today.

The next ticket (per-space conversational agent) produces its answer in a Celery worker, long after the webhook response has gone. That needs the bot to post on its own through the Chat API (`spaces.messages.create`). This ticket adds that outbound path and an authenticated test endpoint, so the credentials and permissions can be proven against a real space before any agent work starts.

`GOOGLE_CHAT_SERVICE_ACCOUNT_EMAIL` (`service-…@gcp-sa-gsuiteaddons.iam.gserviceaccount.com`) cannot be used for this: it is Google-managed, only identifies Google as the sender of inbound events, and no key can be created for it. Outbound calls need a service account we own.

## Decisions

1. **App authentication with our own service account.** The bot posts as itself (`chat.bot` scope), not on behalf of a user, so no OAuth consent flow and no user tokens. The service account must live in the same GCP project as the Chat app. The app must already be a member of the target space; Chat returns 403/404 otherwise.
2. **Mint tokens with PyJWT + httpx, not `google-auth`.** Same reasoning as `GoogleTokenVerifier`: `google-auth` refreshes synchronously and would block the event loop. The JWT-bearer grant is small: sign `{iss, scope, aud, iat, exp}` with the key's RS256 private key (`kid` = `private_key_id`), POST it to the key's `token_uri`, get an `access_token` and `expires_in`. `pyjwt[crypto]` and `httpx` are already dependencies, so nothing new is added.
3. **Client lives in `app/core/`, next to `google_auth.py`.** `GoogleChatClient` is an external-API adapter like `GoogleTokenVerifier`: no FastAPI imports, takes an `httpx.AsyncClient` and the credentials path. The API gets one instance from the lifespan (`app.state.google_chat_client`); the worker in the next ticket builds its own per task with its own httpx client (same pattern as "crawl task opens its own session", GH-5).
4. **Credentials load lazily.** The file is read on the first send, not at startup, so the API boots with `GOOGLE_CHAT_CREDENTIALS_FILE` empty (matches the existing "empty = feature off" style). Empty setting, missing file, or a file without `client_email` / `private_key` / `token_uri` raises `GoogleChatNotConfiguredError` with a message naming the problem, never the key contents.
5. **Token cache.** One access token per client, reused until 60 s before `expires_in`. An `asyncio.Lock` keeps concurrent sends to a single mint. If Chat answers 401 (revoked or clock skew), drop the token, mint once more and retry the call once; a second 401 is a normal error.
6. **Space-level messages only.** `create_message(space, text)` posts `{"text": text}` to `POST https://chat.googleapis.com/v1/{space}/messages`. No thread parameter: the agent's conversation is per (space, user), and threads were explicitly left out. Edit/delete ("Thinking…" then replace) is a later addition to the same client.
7. **Plain text for now.** Chat renders its own lightweight markup (`*bold*`, `_italic_`, links) in `text`. No cards.
8. **Test endpoint: `POST /google-chat/messages`, JWT required.** Body `{space, text}`, response `{"name": "spaces/…/messages/…"}`. Behind `CurrentUser` so random callers cannot post into the organisation's spaces. It stays enabled in all environments (no `DEBUG` gate): auth is the guard, and it is useful for checking production credentials.
9. **Validation.** `space` must match `^spaces/[A-Za-z0-9_-]+$` (stops path tricks like `spaces/x/../..` reaching the URL). `text` is 1–4000 chars after stripping; 4000 is our own cap, comfortably inside Chat's message size limit. Bad input → 422 (normal FastAPI behaviour; this is not the webhook, so no reason to hide the shape).
10. **Error mapping.** `GoogleChatNotConfiguredError` → 503 `"Google Chat sending is not configured"`. Any other `GoogleChatError` (token endpoint rejects, Chat 4xx/5xx, timeout) → 502 `"Google Chat rejected the message (<status>)"`. The log line carries Google's status and error `message` field, never the access token, the assertion, or the key. The client does not retry 5xx: the endpoint is manual, and the worker will own retries (as the embedding task does).
11. **Service function.** `google_chat.send_message(client, space, text) -> str` in `app/services/google_chat.py` logs `google chat sent space=… message=…` and returns the name. The router calls the service, not the client, so the worker can call the same function later.

## Code sketches

`app/core/config.py` (addition)

```python
    # our own service account JSON key, for posting via the Chat API; empty = sending disabled
    google_chat_credentials_file: str = ""
```

`app/core/google_chat_client.py`

```python
import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
import jwt
from fastapi import Request

CHAT_API = "https://chat.googleapis.com/v1"
CHAT_BOT_SCOPE = "https://www.googleapis.com/auth/chat.bot"
TOKEN_LIFETIME = 3600
REFRESH_MARGIN = 60


class GoogleChatError(Exception):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class GoogleChatNotConfiguredError(GoogleChatError):
    pass


@dataclass(frozen=True)
class ServiceAccountCredentials:
    client_email: str
    private_key: str
    private_key_id: str
    token_uri: str

    @classmethod
    def from_file(cls, path: str) -> "ServiceAccountCredentials":
        if not path:
            raise GoogleChatNotConfiguredError("GOOGLE_CHAT_CREDENTIALS_FILE is not set")
        try:
            data = json.loads(Path(path).read_text())
            return cls(
                client_email=data["client_email"],
                private_key=data["private_key"],
                private_key_id=data["private_key_id"],
                token_uri=data["token_uri"],
            )
        except (OSError, ValueError, KeyError) as e:
            raise GoogleChatNotConfiguredError(
                f"unreadable credentials file: {type(e).__name__}"
            ) from e


class GoogleChatClient:
    def __init__(self, http: httpx.AsyncClient, credentials_file: str) -> None:
        self._http = http
        self._credentials_file = credentials_file
        self._creds: ServiceAccountCredentials | None = None
        self._token: str | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def _access_token(self, *, force: bool = False) -> str:
        async with self._lock:
            if force or self._token is None or time.monotonic() >= self._expires_at:
                await self._mint()
            return self._token

    async def _mint(self) -> None:
        # SYNC-EXCEPTION: small local file, read once per client
        creds = self._creds = self._creds or ServiceAccountCredentials.from_file(
            self._credentials_file
        )
        now = int(time.time())
        assertion = jwt.encode(
            {
                "iss": creds.client_email,
                "scope": CHAT_BOT_SCOPE,
                "aud": creds.token_uri,
                "iat": now,
                "exp": now + TOKEN_LIFETIME,
            },
            creds.private_key,
            algorithm="RS256",
            headers={"kid": creds.private_key_id},
        )
        r = await self._post(
            creds.token_uri,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
        )
        body = r.json()
        self._token = body["access_token"]
        self._expires_at = (
            time.monotonic() + body.get("expires_in", TOKEN_LIFETIME) - REFRESH_MARGIN
        )

    async def create_message(self, space: str, text: str) -> str:
        """Posts a message to the space as the app; returns its name (spaces/…/messages/…)."""
        url = f"{CHAT_API}/{space}/messages"
        r = await self._post(url, json={"text": text}, token=await self._access_token())
        if r.status_code == 401:
            r = await self._post(
                url, json={"text": text}, token=await self._access_token(force=True)
            )
        _raise_for_status(r)
        return r.json()["name"]

    # _post: wraps httpx errors into GoogleChatError, adds the bearer header when given;
    # _raise_for_status: non-2xx → GoogleChatError(google's error.message, status)


def get_google_chat_client(request: Request) -> GoogleChatClient:
    return request.app.state.google_chat_client
```

(Exact helper shapes are for implementation; the behaviour is fixed by Decisions 4, 5 and 10.)

`app/schemas/google_chat.py` (additions; plain `BaseModel`, not `ChatModel`, since this is our API, not Google's camelCase payload)

```python
class SendMessageRequest(BaseModel):
    space: str = Field(pattern=r"^spaces/[A-Za-z0-9_-]+$", examples=["spaces/AAAAxxxx"])
    text: str = Field(min_length=1, max_length=4000)

    @field_validator("text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text is blank")
        return v


class SendMessageResponse(BaseModel):
    name: str
```

`app/services/google_chat.py` (addition)

```python
async def send_message(client: GoogleChatClient, space: str, text: str) -> str:
    name = await client.create_message(space, text)
    logger.info(f"google chat sent space={space} message={name}")
    return name
```

`app/routers/google_chat.py`

```python
router = APIRouter(prefix="/google-chat", tags=["google-chat"])

ChatClient = Annotated[GoogleChatClient, Depends(get_google_chat_client)]


@router.post("/messages", response_model=SendMessageResponse)
async def send_message(body: SendMessageRequest, user: CurrentUser, client: ChatClient) -> dict:
    """Testing aid: post a message to a space as the app."""
    try:
        name = await google_chat_service.send_message(client, body.space, body.text)
    except GoogleChatNotConfiguredError as e:
        logger.warning(f"google chat send not configured: {e}")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Google Chat sending is not configured"
        ) from None
    except GoogleChatError as e:
        logger.warning(f"google chat send failed status={e.status}: {e}")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Google Chat rejected the message ({e.status})"
        ) from None
    return {"name": name}
```

`app/main.py` (lifespan)

```python
    async with limiter.redis, httpx.AsyncClient(timeout=10) as http:
        app.state.google_verifier = GoogleTokenVerifier(http)
        app.state.google_chat_client = GoogleChatClient(http, settings.google_chat_credentials_file)
        yield
```

`docs/bruno/send-chat-message.bru`

```
meta {
  name: Send Chat Message
  type: http
  seq: 5
}

post {
  url: {{baseUrl}}/google-chat/messages
  body: json
  auth: bearer
}

auth:bearer {
  token: {{token}}
}

body:json {
  {
    "space": "spaces/REPLACE_ME",
    "text": "Hello from Sapience"
  }
}
```

## Setup (goes into the wiki in slice 3)

1. In the GCP project that hosts the Chat app: IAM & Admin → Service accounts → Create. No project roles are needed; the `chat.bot` scope plus the app's membership in the space is what authorizes posting.
2. Keys → Add key → JSON. Save it as `secrets/google-chat-sa.json` (git-ignored); never commit it.
3. `.env`: `GOOGLE_CHAT_CREDENTIALS_FILE=secrets/google-chat-sa.json`. Restart the API (and later the worker).
4. Make sure the Chat API is enabled in the same project (it already is if events arrive).
5. Space id: open the space in the browser; the URL `https://chat.google.com/room/<id>` gives `spaces/<id>`. The webhook log line (`google chat message space=spaces/…`) shows it too.
6. The app must be in the space (@mention it once or add it via "Apps & integrations").

Risk to confirm in slice 1's manual step: app authentication for a Chat app built as a Workspace add-on. If Chat answers 403 "app not found / not authorized" with valid credentials, check the service account is in the same project number as `GOOGLE_CHAT_SERVICE_ACCOUNT_EMAIL`.

## Files to create/modify

| File | Slice | Purpose |
|------|-------|---------|
| `app/core/config.py` | 1 | `google_chat_credentials_file` |
| `.env.example` | 1 | `GOOGLE_CHAT_CREDENTIALS_FILE=` with a comment |
| `.gitignore` | 1 | `secrets/` |
| `app/core/google_chat_client.py` | 1, 2 | Credentials, token minting, `create_message` (1); cache, lock, 401 retry, error types (2) |
| `app/main.py` | 1 | Client in lifespan; include `google_chat` router |
| `app/schemas/google_chat.py` | 1 | `SendMessageRequest`, `SendMessageResponse` |
| `app/services/google_chat.py` | 1 | `send_message` |
| `app/routers/google_chat.py` | 1, 2 | Test endpoint (1); 503/502 mapping (2) |
| `docs/bruno/send-chat-message.bru` | 1 | Manual request |
| `tests/google_chat_helpers.py` | 1 | Fake service-account key file + `MockTransport` handler for token + Chat endpoints |
| `tests/conftest.py` | 1 | `google_chat_client` fixture overriding `get_google_chat_client` |
| `tests/integration/test_google_chat_send.py` | 1, 2 | Endpoint tests |
| `tests/unit/test_google_chat_client.py` | 2 | Token caching, retry, error mapping at client level |
| `docs/wiki/google-bot.md`, `docs/wiki/index.md` | 3 | Docs |

## Testing plan

No network, same approach as plan 005: an RSA key generated in the test (`new_rsa_key` already exists in `tests/google_chat_helpers.py`) is written into a temp service-account JSON (`tmp_path`). An `httpx.MockTransport` handler answers the token URI and `chat.googleapis.com`, records every request, and can be scripted per test (status, body, counts). The test client does not run the lifespan, so tests override `get_google_chat_client` with a client built on that transport.

**Slice 1 (integration, `test_google_chat_send.py`)**
- Logged-in user posts `{space: "spaces/AAA", text: "hi"}` → 200 `{"name": "spaces/AAA/messages/M1"}`.
  - Token request: form `grant_type` is the JWT-bearer URN; the `assertion` decodes with the test public key and has `iss`, `aud` = token URI, `scope` = `chat.bot`, `kid` header = `private_key_id`.
  - Chat request: `POST /v1/spaces/AAA/messages`, `Authorization: Bearer <minted token>`, JSON `{"text": "hi"}`.
- No / invalid JWT → 401 and no outbound request.
- `space` = `"AAA"`, `"spaces/a/../b"`, `"spaces/"` → 422; `text` = `""`, `"   "`, 4001 chars → 422; nothing sent.

**Slice 2 (unit, `test_google_chat_client.py`, plus endpoint cases)**
- Two `create_message` calls → one token request, two Chat requests.
- Expiry passed (monkeypatch `time.monotonic`) → second call mints again.
- Two concurrent calls (`asyncio.gather`) on a fresh client → one token request.
- Chat 401 then 200 → two token requests, two Chat requests, success. Chat 401 twice → `GoogleChatError(status=401)`.
- Empty path, missing file, JSON missing `private_key` → `GoogleChatNotConfiguredError`; endpoint → 503 with the fixed message, nothing sent to Google.
- Chat 403 / 404 with Google's error JSON → endpoint 502 `"Google Chat rejected the message (403)"`; log has Google's message and no `Bearer`/`assertion`/`PRIVATE KEY` text (caplog-style check on the loguru sink).
- Token endpoint 400 (`invalid_grant`) → 502. `httpx.ConnectTimeout` → 502 with status `None`.

## Verification

- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check .`
- Manual (slice 1): complete Setup, `make dev`, log in via `login.bru`, run `send-chat-message.bru` with a real space id. The message appears in the space from the app, and the response `name` matches the message. Then a space the app is not in → 502 with 403/404; unset `GOOGLE_CHAT_CREDENTIALS_FILE` and restart → 503.
- `git status` shows no key file staged.
