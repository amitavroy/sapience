# Route Google Chat mentions and slash commands to separate handlers (GH-1)

## To-do

Each slice ends in a working, reviewable state with passing tests. Pause for review after each slice.

| # | Slice | Step | Done |
|---|-------|------|------|
| 1 | Split handlers | `app/services/google_chat.py`: `handle_event` only decides the event kind; current logging moves to private `_handle_mention(payload: MessagePayload)`; mention behaviour unchanged | [x] |
| 1 | Split handlers | Tests: `handle_event` with the mention fixture logs the same line as before; payload with neither mention nor command logs nothing and does not raise | [x] |
| 2 | Slash command end-to-end | `app/schemas/google_chat.py`: `AppCommandMetadata`, `AppCommandPayload`, `ChatPayload.app_command_payload` | [x] |
| 2 | Slash command end-to-end | `app/services/google_chat.py`: private `_handle_command(payload: AppCommandPayload)` logs command id, space, sender, stripped `argumentText`; `handle_event` dispatches to it | [x] |
| 2 | Slash command end-to-end | `app/routers/ingest.py`: dispatch and ack when either `message_payload` or `app_command_payload` is present; `{}` only when neither | [x] |
| 2 | Slash command end-to-end | Tests: slash fixture through the endpoint (200 ack, dispatched once, no `systemIdToken` in the enqueued payload); `handle_event` with the slash fixture logs the command line with `text='hello'` | [x] |
| 2 | Slash command end-to-end | Manual: run API + `make worker` via tunnel, run `/add-knowledge hello` in a space, worker log shows the command line; @mention still logs the message line | [ ] |
| 3 | Docs | `docs/wiki/google-bot.md`: document the two event kinds, their payload keys, and where each is handled | [ ] |

## Context

The Google Chat webhook (GH-2, plan 005) accepts @mentions: Google POSTs `chat.messagePayload`, the endpoint verifies the token, enqueues `process_chat_event`, and the worker's `handle_event` logs the message.

Slash commands arrive differently. A captured payload is in `tests/fixtures/google-slash-command.json`. The envelope (`commonEventObject`, `authorizationEventObject`, `chat.user`, `chat.eventTime`) is identical, but the body sits under `chat.appCommandPayload` instead of `chat.messagePayload`:

| | @mention | Slash command |
|---|---|---|
| Body key under `chat` | `messagePayload` | `appCommandPayload` |
| Extra metadata | none | `appCommandMetadata` (`appCommandType: SLASH_COMMAND`, `appCommandId`) |
| `message.text` | `@Sapience hi` | `/add-knowledge hello` |
| `message.argumentText` | ` hi` | ` hello` |
| `annotations[0].type` | `USER_MENTION` | `SLASH_COMMAND` (`commandName`, `commandId`) |

`space` and `message` have the same shape in both, so `ChatSpace` / `ChatMessage` are reused. Today a slash command is parsed but ignored: `appCommandPayload` falls into pydantic `extra`, `handle_event` returns early, and the router returns `{}` without dispatching because `message_payload is None`.

This ticket makes both kinds reach the worker and be handled by their own function. Handlers only log for now; ingesting the `/add-knowledge` text into the RAG pipeline is a later ticket that plugs into `_handle_command`.

## Decisions

1. **`handle_event` is a pure dispatcher.** It checks which payload is set and calls one handler. It does no logging itself, so each handler owns its own logging and behaviour.
2. **Handlers are private.** `_handle_mention` and `_handle_command` are only called from `handle_event`, so they get a leading underscore. `handle_event` keeps its signature, so the Celery task needs no change.
3. **Dispatch on the key, not the text.** The discriminator is which of `message_payload` / `app_command_payload` is set. Not text parsing, not annotation types. If both were ever set, mention wins (not expected from Google).
4. **Model `appCommandPayload` explicitly.** Relying on `extra="allow"` would mean untyped dict access in the handler. `AppCommandMetadata.app_command_id` is typed `int`; Google sends `1.0`, which pydantic's lax mode coerces because the float is whole.
5. **Route on `appCommandId`, later.** When more commands exist, route on `app_command_metadata.app_command_id` (the ID registered in the Chat API console), not on the command name text. Out of scope here: only one command exists and it just logs.
6. **Endpoint acks slash commands too.** The router dispatches and returns the same "Got it" reply when either payload is present. Only events with neither (e.g. added to a space) keep returning `{}` and are not queued.
7. **Same text extraction.** Both handlers use `(msg.argument_text or msg.text).strip()` and the sender email, as the mention path does today. `argumentText` already excludes the `@Sapience` / `/add-knowledge` prefix.
8. **Log lines are distinct.** Mention keeps `google chat message space=... sender=... text=...`. Command logs `google chat command id=<id> space=... sender=... text=...`, so the worker log shows which path ran.

## Code sketches

`app/schemas/google_chat.py` (additions)

```python
class AppCommandMetadata(ChatModel):
    app_command_id: int
    app_command_type: str  # SLASH_COMMAND


class AppCommandPayload(ChatModel):
    space: ChatSpace
    message: ChatMessage
    app_command_metadata: AppCommandMetadata


class ChatPayload(ChatModel):
    user: ChatUser | None = None
    event_time: datetime | None = None
    message_payload: MessagePayload | None = None  # @mention
    app_command_payload: AppCommandPayload | None = None  # slash command
```

`app/services/google_chat.py`

```python
async def handle_event(chat: ChatPayload) -> None:
    """Runs in the worker. Decides what kind of event this is and delegates."""
    if chat.message_payload is not None:
        await _handle_mention(chat.message_payload)
    elif chat.app_command_payload is not None:
        await _handle_command(chat.app_command_payload)
    # anything else (e.g. added to a space): nothing to process


async def _handle_mention(payload: MessagePayload) -> None:
    msg = payload.message
    sender = msg.sender.email if msg.sender else None
    text = (msg.argument_text or msg.text).strip()
    logger.info(f"google chat message space={payload.space.name} sender={sender} text={text!r}")


async def _handle_command(payload: AppCommandPayload) -> None:
    msg = payload.message
    sender = msg.sender.email if msg.sender else None
    text = (msg.argument_text or msg.text).strip()
    command_id = payload.app_command_metadata.app_command_id
    logger.info(
        f"google chat command id={command_id} space={payload.space.name} "
        f"sender={sender} text={text!r}"
    )
```

`app/routers/ingest.py` (condition change)

```python
    chat = event.chat
    if chat is None or (chat.message_payload is None and chat.app_command_payload is None):
        return {}  # neither a message nor a command (e.g. added to a space)
```

## Files to create/modify

| File | Slice | Purpose |
|------|-------|---------|
| `app/services/google_chat.py` | 1, 2 | `handle_event` dispatcher + `_handle_mention` (1); `_handle_command` (2) |
| `app/schemas/google_chat.py` | 2 | `AppCommandMetadata`, `AppCommandPayload`, `ChatPayload.app_command_payload` |
| `app/routers/ingest.py` | 2 | Dispatch and ack slash commands |
| `tests/fixtures/google-slash-command.json` | 2 | Already captured; sanitize (real customer id, token) and commit |
| `tests/unit/test_google_chat_task.py` | 1, 2 | Handler dispatch + log assertions for both fixtures |
| `tests/integration/test_google_chat.py` | 2 | Slash command through the endpoint |
| `docs/wiki/google-bot.md` | 3 | Document the two event kinds |

## Testing plan

Reuse the existing helpers: `load_fixture` in `tests/conftest.py`, the test-signed token fixtures and the monkeypatched `dispatch` from plan 005.

**Unit (`tests/unit/test_google_chat_task.py`)**
- Mention fixture → `handle_event` logs `google chat message ... text='hi'` and not a command line.
- Slash fixture → `handle_event` logs `google chat command id=1 ... text='hello'` and not a message line.
- Payload with neither key → nothing logged, no exception.
- `app_command_id` of `1.0` in the fixture parses to `1`.

**Integration (`tests/integration/test_google_chat.py`)**
- Slash fixture with a valid signed token → 200 with the "Got it" body, `dispatch` called once, enqueued payload contains `appCommandPayload` and no `systemIdToken`.
- Existing mention and "no payload → `{}`" tests still pass unchanged.

**Fixture hygiene.** `google-slash-command.json` contains `customers/C03qjrsqa`, which looks real. Replace it with a placeholder like the other IDs before committing.

## Verification

- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check .`
- Manual: `make dev` + `make worker` behind the tunnel (setup as in `docs/wiki/google-bot.md`). Register `/add-knowledge` in the Chat API console, run `/add-knowledge hello` in a space, and check the worker log shows `google chat command id=... text='hello'`. @mention the app and check it still logs the message line.
