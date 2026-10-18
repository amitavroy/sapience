# Verified Google Chat webhook at POST /ingest/google-chat (GH-2)

## To-do

Each slice ends in a working, reviewable state with passing tests. Pause for review after each slice.

| # | Slice | Step | Done |
|---|-------|------|------|
| 1 | Verified ack | Deps: `pyjwt` → `pyjwt[crypto]`, move `httpx` from dev to main deps; `uv sync` | [x] |
| 1 | Verified ack | Settings `google_chat_audience`, `google_chat_service_account_email` in `app/core/config.py` + `.env.example` | [x] |
| 1 | Verified ack | `app/core/google_auth.py`: `GoogleTokenVerifier` (async JWKS fetch + cache + refetch on unknown `kid`), `InvalidGoogleTokenError`, `get_google_verifier` dependency | [x] |
| 1 | Verified ack | `app/main.py` lifespan: one shared `httpx.AsyncClient`, build verifier, close on shutdown | [x] |
| 1 | Verified ack | Minimal `app/schemas/google_chat.py` (`GoogleChatEvent` with `authorizationEventObject.systemIdToken`) | [x] |
| 1 | Verified ack | `app/tasks/google_chat.py`: Celery task `process_chat_event(chat: dict)` (stub: logs receipt); add `app.tasks.google_chat` to `include` in `app/core/celery_app.py` | [x] |
| 1 | Verified ack | `app/routers/ingest.py`: `POST /ingest/google-chat`, verifies token (401 on failure), `dispatch`es the chat payload (token stripped) to the worker, returns the sync "Got it" add-on reply; register router | [x] |
| 1 | Verified ack | Tests: `tests/unit/test_google_auth.py` (verifier cases) + `tests/integration/test_google_chat.py` (valid → 200 ack + task dispatched; missing / invalid / unconfigured → 401 + nothing dispatched) | [x] |
| 1 | Verified ack | Manual: run API + `make worker` via ngrok, @mention the app, it replies "Got it" and the worker log shows the event | [x] |
| 2 | Parse + log | Full schemas from the real payload (`ChatPayload`, `ChatUser`, `MessagePayload`, `ChatSpace`, `ChatMessage`) | [x] |
| 2 | Parse + log | `app/services/google_chat.py`: `handle_event(chat)` logs sender/space/stripped `argumentText`; called by the worker task. Endpoint replies `{}` instead of "Got it" for non-message events | [x] |
| 2 | Parse + log | Sanitize `tests/fixtures/google-chat-incoming.json`, add `load_fixture` helper, drive integration tests from the fixture; non-message event test; task body test | [x] |
| 3 | Docs | `docs/wiki/google-bot.md`: full write-up with installation notes (Google Cloud / Chat API console setup, env vars, local tunnel testing, how verification works, rate-limit risk) | [x] |
| 3 | Docs | `docs/wiki/index.md`: add only a short "Google Chat webhook" entry that links to `google-bot.md`; no details there | [x] |

## Context

We have a Google Chat app, built on the Chat API as a Google Workspace add-on. When someone @mentions it in a space, Google sends an HTTP POST to our configured endpoint. Each event includes `authorizationEventObject.systemIdToken`. This is an OIDC ID token signed by Google, and it is the only proof that the request came from Google for *our* app. Without verification, anyone who knows the URL could inject events.

This ticket adds the endpoint `POST /ingest/google-chat`, verifies the token, acknowledges verified events with a short synchronous Chat reply, and hands the event to a Celery worker. The request path does nothing but verify, enqueue and ack; all processing happens in the worker. The real processing (feeding messages into the RAG pipeline from GH-1) comes in later tickets and plugs into the same task.

A real event was captured in `tests/fixtures/google-chat-incoming.json`. Its decoded token:

```json
// header
{"alg": "RS256", "kid": "943a3a5d…", "typ": "JWT"}
// claims
{
  "aud": "https://<ngrok-host>/ingest/google-chat",
  "azp": "<numeric id>",
  "email": "service-<project-number>@gcp-sa-gsuiteaddons.iam.gserviceaccount.com",
  "email_verified": true,
  "exp": <iat + 3600>,
  "iat": <issued at>,
  "iss": "https://accounts.google.com",
  "sub": "<numeric id>"
}
```

This confirms the claims our checks rely on:
- `aud` is the endpoint URL
- `iss` is `https://accounts.google.com`
- `email` is the add-on service account

## Decisions

1. **Verify against Google's JWKS with async httpx, not `PyJWKClient` or `google-auth`.** Both of those make blocking HTTP calls (urllib / requests), which `docs/architecture/index.md` forbids inside `async def`. We fetch `https://www.googleapis.com/oauth2/v3/certs` with `httpx.AsyncClient` and use PyJWT only for the cryptography (`jwt.PyJWK`, `jwt.decode`). RS256 needs `cryptography`, so the dependency becomes `pyjwt[crypto]`.
2. **One shared HTTP client.** The `httpx.AsyncClient(timeout=10)` is created in the app lifespan and closed on shutdown, following the "one shared client" rule.
3. **JWKS caching.** Keys are cached until the `Cache-Control: max-age` of the certs response expires (1h if the header is missing).
   - An unknown `kid` forces one refetch, because Google rotates keys.
   - An `asyncio.Lock` makes sure concurrent requests trigger only one fetch.
4. **Claims checked:**
   - RS256 signature
   - `exp` (PyJWT default leeway 0; can add a small leeway if clock skew shows up)
   - `iss == "https://accounts.google.com"`
   - `aud == GOOGLE_CHAT_AUDIENCE`
   - `email_verified is True`
   - `email == GOOGLE_CHAT_SERVICE_ACCOUNT_EMAIL`

   The email check stops a Google token minted for a different project that happens to share our audience.
5. **Fail closed.** Each of these gets a 401 and is logged as a warning, without logging the token:
   - an empty `GOOGLE_CHAT_AUDIENCE` or `GOOGLE_CHAT_SERVICE_ACCOUNT_EMAIL`
   - a missing token or malformed body
   - any verification error
   - a JWKS fetch failure

   A malformed body gets 401, not 422, so an unauthenticated caller learns nothing about the expected payload shape.
6. **Reply format.** Workspace add-on Chat apps answer through `hostAppDataAction`, not the legacy `{"text": ...}` body:
   ```json
   {"hostAppDataAction": {"chatDataAction": {"createMessageAction": {"message": {"text": "Got it"}}}}}
   ```
   Events without `chat.messagePayload` (e.g. added to space) get `{}`.
7. **Loose schemas.** Pydantic models use camelCase aliases (`alias_generator=to_camel`, `populate_by_name=True`) and `extra="allow"`. Only the fields we use are modelled, so new Google fields don't break parsing. Google sends numbers as floats (`1.0`, annotation indexes), and leaving them unmodelled avoids type friction.
8. **`argumentText` is stripped.** Google sends the text after the mention with a leading space (`" hi"`).
9. **Settings, not hard-coded values.**
   - The audience is the public endpoint URL, so it changes per environment (ngrok locally, the real host in prod).
   - The service-account email is tied to the GCP project number.
10. **Rate limit unchanged in this ticket.** The global per-IP `rate_limit` dependency also applies here. Google sends from a small IP pool, so 60/min could throttle busy spaces. This is recorded as a known risk with a possible follow-up: exempt `/ingest/*` or give it its own limit.
11. **Verify in the request, process in the worker.**
    - The endpoint verifies the token inline (cached keys, no DB), so bad callers get 401 and never reach the queue. It then calls `dispatch(process_chat_event, chat_dict)` and returns the synchronous "Got it" reply.
    - Only `event.chat` is enqueued (`model_dump(mode="json", by_alias=True)`); the `systemIdToken` is never written to Redis.
    - The task is a sync Celery task wrapping an async body in `asyncio.run`, like `app/tasks/user.py`. It is registered in `include=[...]` in `celery_app.py`.
    - `task_acks_late` means a task can run twice, and Google also retries, so tasks must be idempotent. The message `name` is the dedup key for later ingestion.
    - If the broker is down, `dispatch` raises and the endpoint returns 500, so Google retries. This is accepted rather than swallowed.
    - Per the logging wiki, `trace_id` is passed to the task and wrapped in `logger.contextualize(trace_id=..., job="process_chat_event")`.

## Code sketches

`app/core/config.py` (additions)

```python
    # Google Chat add-on webhook; empty = endpoint rejects everything
    google_chat_audience: str = ""  # exact HTTP endpoint URL set in the Chat API console
    google_chat_service_account_email: str = ""  # service-<project-number>@gcp-sa-gsuiteaddons...
```

`app/core/google_auth.py`

```python
GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUER = "https://accounts.google.com"
DEFAULT_MAX_AGE = 3600


class InvalidGoogleTokenError(Exception):
    pass


class GoogleTokenVerifier:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http
        self._keys: dict[str, jwt.PyJWK] = {}
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def _refresh(self) -> None:
        r = await self._http.get(GOOGLE_CERTS_URL)
        r.raise_for_status()
        self._keys = {k["kid"]: jwt.PyJWK(k) for k in r.json()["keys"]}
        self._expires_at = time.monotonic() + _max_age(r.headers.get("cache-control"))

    async def _key(self, kid: str, *, force: bool = False) -> jwt.PyJWK | None:
        async with self._lock:
            if force or time.monotonic() >= self._expires_at:
                await self._refresh()
            return self._keys.get(kid)

    async def verify(self, token: str, *, audience: str, email: str) -> dict:
        if not audience or not email:
            raise InvalidGoogleTokenError("google chat verification not configured")
        try:
            kid = jwt.get_unverified_header(token).get("kid", "")
            key = await self._key(kid) or await self._key(kid, force=True)
            if key is None:
                raise InvalidGoogleTokenError(f"unknown kid {kid}")
            claims = jwt.decode(
                token, key, algorithms=["RS256"], audience=audience, issuer=GOOGLE_ISSUER
            )
        except (jwt.InvalidTokenError, httpx.HTTPError, KeyError, ValueError) as e:
            raise InvalidGoogleTokenError(str(e)) from e
        if claims.get("email_verified") is not True or claims.get("email") != email:
            raise InvalidGoogleTokenError("unexpected token email")
        return claims


def get_google_verifier(request: Request) -> GoogleTokenVerifier:
    return request.app.state.google_verifier
```

The `force=True` call refetches only when the `kid` is unknown after a normal lookup. A failed refetch doesn't block that one request for long: the lock is released, and the next request retries because `_expires_at` was not advanced.

`app/main.py` (lifespan)

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info(f"starting {settings.app_name}")
    async with limiter.redis, httpx.AsyncClient(timeout=10) as http:
        app.state.google_verifier = GoogleTokenVerifier(http)
        yield
    await engine.dispose()
    logger.info("shutdown complete")
```

`app/schemas/google_chat.py`

```python
class ChatModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="allow")


class AuthorizationEventObject(ChatModel):
    system_id_token: str


class ChatUser(ChatModel):
    name: str
    display_name: str | None = None
    email: str | None = None
    type: str | None = None  # HUMAN | BOT


class ChatSpace(ChatModel):
    name: str
    display_name: str | None = None
    type: str | None = None


class ChatThread(ChatModel):
    name: str


class ChatMessage(ChatModel):
    name: str
    text: str = ""
    argument_text: str | None = None
    sender: ChatUser | None = None
    thread: ChatThread | None = None


class MessagePayload(ChatModel):
    space: ChatSpace
    message: ChatMessage


class ChatPayload(ChatModel):
    user: ChatUser | None = None
    event_time: datetime | None = None
    message_payload: MessagePayload | None = None


class GoogleChatEvent(ChatModel):
    authorization_event_object: AuthorizationEventObject
    chat: ChatPayload | None = None
```

In slice 1 only `GoogleChatEvent.authorization_event_object` and a bare `chat` are needed. Slice 2 fills in the rest.

`app/core/deps.py` (next to `CurrentUser`, the repo's other auth dependency)

```python
Verifier = Annotated[GoogleTokenVerifier, Depends(get_google_verifier)]


async def get_verified_chat_event(request: Request, verifier: Verifier) -> GoogleChatEvent:
    try:
        event = GoogleChatEvent.model_validate(await request.json())
        await verifier.verify(
            event.authorization_event_object.system_id_token,
            audience=settings.google_chat_audience,
            email=settings.google_chat_service_account_email,
        )
    except (ValueError, ValidationError, InvalidGoogleTokenError) as e:
        logger.warning(f"google chat event rejected: {e}")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid Google Chat request") from None
    return event


VerifiedChatEvent = Annotated[GoogleChatEvent, Depends(get_verified_chat_event)]
```

`ValueError` covers a body that isn't valid JSON (`json.JSONDecodeError` subclasses it).

`app/routers/ingest.py`

```python
router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/google-chat")
async def google_chat(event: VerifiedChatEvent) -> dict:
    if event.chat is None or event.chat.message_payload is None:
        return {}  # not a message (e.g. added to a space): nothing to ack or queue
    # the token is not enqueued, only the chat payload
    await dispatch(
        process_chat_event,
        event.chat.model_dump(mode="json", by_alias=True, exclude_unset=True),
        trace_id.get(),
    )
    return google_chat_service.reply(google_chat_service.ACK)
```

`app/tasks/google_chat.py`

```python
@celery_app.task
def process_chat_event(chat: dict, trace_id: str) -> None:
    # SYNC-EXCEPTION: Celery task bodies are sync; asyncio.run drives the async work
    with logger.contextualize(trace_id=trace_id, job="process_chat_event"):
        asyncio.run(google_chat_service.handle_event(ChatPayload.model_validate(chat)))
```

In slice 1 the task body only logged that an event arrived. Slice 2 validates the payload and calls `handle_event`. `trace_id` is the `ContextVar` from `app/core/trace.py`, already set by the request-log middleware.

`app/services/google_chat.py`

```python
ACK = "Got it"


async def handle_event(chat: ChatPayload) -> None:
    payload = chat.message_payload
    if payload is None:
        return
    msg = payload.message
    sender = msg.sender.email if msg.sender else None
    text = (msg.argument_text or msg.text).strip()
    logger.info(f"google chat message space={payload.space.name} sender={sender} text={text!r}")


def reply(text: str) -> dict:
    return {
        "hostAppDataAction": {
            "chatDataAction": {"createMessageAction": {"message": {"text": text}}}
        }
    }
```

## Files to create/modify

| File | Slice | Purpose |
|------|-------|---------|
| `pyproject.toml`, `uv.lock` | 1 | `pyjwt[crypto]`; `httpx` to main deps |
| `app/core/config.py`, `.env.example` | 1 | `GOOGLE_CHAT_AUDIENCE`, `GOOGLE_CHAT_SERVICE_ACCOUNT_EMAIL` |
| `app/core/google_auth.py` | 1 | `GoogleTokenVerifier`, `InvalidGoogleTokenError`, `get_google_verifier` |
| `app/main.py` | 1 | Shared httpx client + verifier in lifespan; include `ingest` router |
| `app/core/deps.py` | 1 | `get_verified_chat_event` dependency + `VerifiedChatEvent` alias, next to `CurrentUser` |
| `app/routers/ingest.py` | 1 | `POST /ingest/google-chat`; dispatches to the worker |
| `app/tasks/google_chat.py`, `app/core/celery_app.py` | 1 | `process_chat_event` task (stub in 1, real in 2); add module to `include` |
| `app/schemas/google_chat.py` | 1, 2 | Minimal event model (1); full payload models (2) |
| `app/services/google_chat.py` | 1, 2 | `reply()` / `ACK` (1); `handle_event` parse + log, called by the task (2) |
| `tests/unit/test_google_auth.py` | 1 | Verifier unit tests |
| `tests/integration/test_google_chat.py` | 1, 2 | Endpoint tests |
| `tests/conftest.py` | 1, 2 | Test RSA key / token-signing fixtures (1); `load_fixture` helper (2) |
| `tests/fixtures/google-chat-incoming.json` | 2 | Sanitized real payload |
| `docs/wiki/google-bot.md` | 3 | Details and installation notes: console setup, env vars, local tunnel testing, verification, rate-limit risk |
| `docs/wiki/index.md` | 3 | Entry only: short "Google Chat webhook" summary linking to `google-bot.md` |

## Testing plan

No real network calls. Tests generate an RSA key pair with `cryptography`. Its public JWK (with a `kid`) is served through `httpx.MockTransport`, and tokens are signed with `jwt.encode(..., algorithm="RS256", headers={"kid": ...})`. The claims mirror the real token (see Context).

**Fixtures in `tests/conftest.py`:**
- `rsa_key`: the key pair plus its JWK
- `sign_google_token(**overrides)`: valid claims by default
- `google_settings`: uses `monkeypatch` to set the audience and email on `settings`
- an override of `get_google_verifier` that returns a verifier backed by the mock transport. The `client` fixture doesn't run the lifespan, so `app.state` is never set and this override is required.

**Unit: `tests/unit/test_google_auth.py`**
- A valid token returns its claims.
- Each of these is rejected:
  - bad signature (signed with a different key)
  - wrong `aud`
  - wrong `iss`
  - expired
  - wrong `email`
  - `email_verified: false`
  - missing `kid`
  - garbage string
- An unknown `kid` triggers one refetch. After rotation (the mock serves the new key on its second call), the token passes.
- A second verify within `max-age` makes no extra HTTP call (count transport calls).
- A JWKS 500 or a timeout raises `InvalidGoogleTokenError`.
- An empty audience or email raises `InvalidGoogleTokenError`.

**Integration: `tests/integration/test_google_chat.py`**
- `dispatch` is monkeypatched on the router module to record calls, so no broker is needed.
- The fixture payload with a test-signed token → 200, with a body equal to the "Got it" `hostAppDataAction`, and `dispatch` called once with the task and the chat payload. The enqueued payload does not contain the `systemIdToken`.
- Each of these → 401 and `dispatch` not called:
  - `authorizationEventObject` removed
  - invalid token
  - non-JSON body
  - `GOOGLE_CHAT_AUDIENCE` empty
- Slice 2: an event without `messagePayload` → 200 `{}`.

**Task: `tests/unit/test_google_chat_task.py` (slice 2)**
- Call `handle_event` directly with the sanitized fixture's `chat` payload and check the log contains space, sender and the stripped `argumentText`.
- A payload without `messagePayload` logs nothing and does not raise.

**Fixture hygiene (slice 2).** The captured fixture holds:
- a real user email, avatar URLs and customer/space IDs
- the project's service-account email
- a signed ID token

The token expires an hour after it was issued, so it isn't a lasting secret, but the fixture is still sanitized before it is committed:
- users become `ann@example.com`-style placeholders
- IDs become placeholders
- `systemIdToken` becomes `"PLACEHOLDER"` (tests overwrite it anyway)

## Verification

- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check .`
- Manual (slice 1):
  1. `make dev` and, in a second terminal, `make worker` (Redis must be running). Then expose port 8000 with ngrok (or cloudflared).
  2. In the Google Cloud console → Chat API → Configuration, set the HTTP endpoint URL to `https://<tunnel-host>/ingest/google-chat`.
  3. Set `.env`: `GOOGLE_CHAT_AUDIENCE` to that same URL, and `GOOGLE_CHAT_SERVICE_ACCOUNT_EMAIL=service-<project-number>@gcp-sa-gsuiteaddons.iam.gserviceaccount.com`.
  4. @mention the app in a space. It replies "Got it" straight away, and the worker log (not the API log) shows the event with the same trace id as the request.
  5. `curl -X POST https://<tunnel-host>/ingest/google-chat -H 'Content-Type: application/json' -d '{"authorizationEventObject":{"systemIdToken":"x"}}'` → 401.
  6. Restart with `GOOGLE_CHAT_AUDIENCE` set to a different URL and @mention again. The app does not reply and the log shows a rejected event.
