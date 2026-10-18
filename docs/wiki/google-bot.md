# Google Chat webhook

Google Chat sends every @mention and every slash command of our app to `POST /ingest/google-chat`. The endpoint proves the request came from Google, answers "Got it" straight away, and hands the event to a Celery worker.

    Google Chat → POST /ingest/google-chat
                      │
                      ├─ verify ID token ── fails → 401, nothing queued
                      ├─ no mention and no slash command in the event → 200 {}
                      └─ mention or slash command → dispatch process_chat_event → 200 "Got it"
                                        │
                                        └─ worker: handle_event
                                              ├─ messagePayload → _handle_mention
                                              └─ appCommandPayload → _handle_command

| Case | Status | Body | Queued |
|------|--------|------|--------|
| Verified event with a mention or a slash command | 200 | "Got it" add-on reply | yes |
| Verified event with neither (e.g. app added to a space) | 200 | `{}` | no |
| Missing or malformed body, missing or invalid token, token for another audience or service account, expired token | 401 | `Invalid Google Chat request` | no |
| `GOOGLE_CHAT_AUDIENCE` or `GOOGLE_CHAT_SERVICE_ACCOUNT_EMAIL` empty | 401 | same | no |
| Broker (Redis) down | 500 | | no |

- The app is a Google Workspace add-on, so the reply is a `hostAppDataAction` body, not the legacy `{"text": ...}` shape.
- A malformed body gets 401, not 422, so an unauthenticated caller learns nothing about the expected payload.
- For a 401, the log has one warning (`google chat event rejected: ...`) and never the token.
- On a 500 from a down broker, Google retries the event.

# Event kinds

Both kinds share the same envelope (`commonEventObject`, `authorizationEventObject`, `chat.user`, `chat.eventTime`). The body sits under a different key of `chat`, and that key is the only thing used to tell them apart.

| | @mention | Slash command |
|---|---|---|
| Key under `chat` | `messagePayload` | `appCommandPayload` |
| Extra metadata | none | `appCommandMetadata` (`appCommandId`, `appCommandType: SLASH_COMMAND`) |
| `message.text` | `@Sapience hi` | `/add-knowledge hello` |
| `message.argumentText` | ` hi` | ` hello` |
| `message.annotations[0].type` | `USER_MENTION` | `SLASH_COMMAND` |
| Handled by | `_handle_mention` | `_handle_command` |

- `space` and `message` have the same shape in both, so the same `ChatSpace` / `ChatMessage` models are used.
- A slash command arrives only as `appCommandPayload`; it is not also sent as a mention.
- `appCommandId` is the ID registered for the command in the Chat API console. Google sends it as a float (`1.0`); the model reads it as an int. When more commands exist, route on this ID, not on the command text.
- If both keys were ever present, the mention wins.

# How the request is verified

Each event carries `authorizationEventObject.systemIdToken`, an RS256 ID token signed by Google. It is the only proof the request is from Google for our app, so every check must pass:

| Check | Expected |
|-------|----------|
| Signature | Valid against Google's published keys (`https://www.googleapis.com/oauth2/v3/certs`) |
| `iss` | `https://accounts.google.com` |
| `aud` | `GOOGLE_CHAT_AUDIENCE` |
| `exp` | Present and not expired |
| `email_verified` | `true` |
| `email` | `GOOGLE_CHAT_SERVICE_ACCOUNT_EMAIL` |

- The `email` check stops a Google token minted for a different project that happens to share our audience.
- Keys are fetched with an async `httpx` client (PyJWT and `google-auth` fetch synchronously and would block the event loop). They are cached until the certs response's `Cache-Control: max-age` expires, or 1 hour if the header is missing.
- An unknown `kid` forces one refetch, because Google rotates keys. A lock keeps concurrent requests to a single fetch.
- A failed key fetch (HTTP error or timeout) is treated as a rejected token.
- The verifier and its shared HTTP client are created in the app lifespan (`app.state.google_verifier`) and closed on shutdown. The dependency is `get_verified_chat_event` in `app/core/deps.py`.
- A token with no `kid` is rejected without a fetch. An unknown `kid` does cost one fetch to Google per request, so the per-IP rate limit is the only brake on a caller sending random `kid`s.

# What the worker does

The endpoint enqueues only the `chat` part of the event, exactly as Google sent it. The ID token is never written to Redis.

- Task: `process_chat_event(chat, trace_id)` in `app/tasks/google_chat.py`. It validates the payload into `ChatPayload`, then runs `handle_event` in `app/services/google_chat.py`.
- `handle_event` only decides the event kind and delegates to a private handler; each handler does its own logging.
  - `_handle_mention` logs `google chat message space=... sender=... text=...`.
  - `_handle_command` logs `google chat command id=... space=... sender=... text=...`.
  - In both, the text is `argumentText` (what follows the @mention or the command name) stripped of its leading space, or the full text if there is none.
  - An event with neither payload is ignored.
- Ingesting messages and `/add-knowledge` content into the RAG pipeline is a later ticket and plugs into these two handlers.
- The request's trace id is passed to the task, so worker log lines carry the same `trace_id` as the request. The job name is `process_chat_event`.
- Tasks are acknowledged late, so a task can run twice, and Google also retries failed events. Anything the task does later must be idempotent; the message `name` (for example `spaces/AAA/messages/BBB`) is the natural dedup key.
- Payload models (`app/schemas/google_chat.py`) use camelCase aliases and keep unknown fields, so new fields from Google do not break parsing. A DM has no space `displayName` and no mention annotations; both are optional.

# Installation

You need a Google Cloud project with the Chat API enabled and a Chat app configured with an HTTP endpoint, plus a public HTTPS URL that reaches this app.

## 1. Environment variables

Both default to empty, and while either is empty the endpoint rejects every request with 401.

| Variable | Value |
|----------|-------|
| `GOOGLE_CHAT_AUDIENCE` | The exact HTTP endpoint URL set in the Chat API console, for example `https://<host>/ingest/google-chat`. It changes per environment (tunnel locally, the real host in production) |
| `GOOGLE_CHAT_SERVICE_ACCOUNT_EMAIL` | `service-<project-number>@gcp-sa-gsuiteaddons.iam.gserviceaccount.com`, tied to the project number of the Google Cloud project |

- If you are unsure of either value, `aud` and `email` are claims in the ID token of a real event. Decode the middle segment of a captured token (base64url JSON) and copy them. Do not paste a live token anywhere shared.
- A trailing slash or `http` vs `https` mismatch in the audience gives a 401.

## 2. Google Cloud console

1. Enable the Google Chat API for the project.
2. Open Chat API → Configuration.
3. Set the app's HTTP endpoint URL to `https://<host>/ingest/google-chat`. Use the same URL as `GOOGLE_CHAT_AUDIENCE`.
4. Make the app available to the people or spaces that should use it, and save.

## 3. Run the services

The API and the worker are separate processes, and both need Redis (rate limiter and queue).

    make dev       # API
    make worker    # Celery worker; without it messages are queued but never processed

# Testing locally with a tunnel

1. Start Redis, then `make dev` and `make worker`.
2. Expose port 8000 with ngrok or cloudflared, for example `ngrok http 8000`.
3. Set the Chat API console endpoint URL to `https://<tunnel-host>/ingest/google-chat` and `GOOGLE_CHAT_AUDIENCE` in `.env` to the same URL. Restart the API after changing `.env`.
4. @mention the app in a space, or message it in a DM. It replies "Got it" immediately, and the worker log (not the API log) shows the event with the request's trace id.
5. To test slash commands, register `/add-knowledge` in the Chat API console (Configuration → Commands, command ID 1), then run `/add-knowledge hello` in a space. The worker log shows `google chat command id=1 ... text='hello'`.
6. Check that unauthenticated callers are refused:

       curl -X POST https://<tunnel-host>/ingest/google-chat \
         -H 'Content-Type: application/json' \
         -d '{"authorizationEventObject":{"systemIdToken":"x"}}'

   Expected: 401.
7. Set `GOOGLE_CHAT_AUDIENCE` to a different URL, restart, and @mention again. The app does not reply and the API log shows a rejected event.

Free ngrok URLs and the audience must stay in step: a new tunnel host means updating both the console and `.env`.

# Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| App never replies, log shows `google chat event rejected` | The warning text says why: wrong audience (`Audience doesn't match`), wrong service account (`unexpected token email`), expired token, unknown key, or empty settings (`google chat verification not configured`) |
| App replies "Got it" but nothing in any log | The worker is not running, or it was started before `.env` or the code changed |
| 500 on every event | Redis or the broker is unreachable |
| 429 from busy spaces | See Rate limit |

# Rate limit

The global per-IP `rate_limit` dependency applies to this endpoint too (default `60/minute`, see Request pipeline). Google sends from a small pool of IPs, and behind a proxy or tunnel the client IP may be one shared address, so a busy space could be throttled with 429s. This is a known risk, left unchanged in this ticket. The likely follow-up is to exempt `/ingest/*` or give it its own limit.

# Tests

No test makes a network call. Tokens are signed with a throwaway RSA key, and Google's certs endpoint is replaced by `httpx.MockTransport` (`tests/google_chat_helpers.py`, fixtures in `tests/conftest.py`). Three real captured events, a space message, a DM and a slash command (`google-slash-command.json`), are stored sanitized in `tests/fixtures/` and drive the endpoint and worker tests. The test client does not run the app lifespan, so tests override `get_google_verifier`.
