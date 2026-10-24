# Add per-space conversational agent to FocalBot with LangGraph (GH-7)

## To-do

Each slice ends in a working, reviewable state with passing tests. Pause for review after each slice. Requires GH-6 (plan 011) merged: `GoogleChatClient` and `google_chat.send_message`.

| # | Slice | Step | Done |
|---|-------|------|------|
| 1 | Bot answers with memory | Deps: `langgraph`, `langchain`, `langchain-openai`, `langgraph-checkpoint-postgres`, `psycopg[binary]` | [x] |
| 1 | Bot answers with memory | `app/core/config.py` + `.env.example`: `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_CHAT_MODEL`, `LLM_SUMMARY_MODEL`, `LLM_TIMEOUT_SECONDS` | [x] |
| 1 | Bot answers with memory | `app/agent/models.py`: `get_model(role)` factory (not cached; see Decision 7) | [x] |
| 1 | Bot answers with memory | `app/agent/state.py`, `prompts.py`, `graph.py`: `ConversationState`, system prompt, `build_graph(checkpointer)` = `agent` (`create_agent` subgraph, no tools yet) → `finalize` | [x] |
| 1 | Bot answers with memory | `app/agent/checkpointer.py`: `open_checkpointer()` (AsyncPostgresSaver from `DATABASE_URL`); `uv run cli setup-checkpointer`; `make migrate` runs it after Alembic | [x] |
| 1 | Bot answers with memory | `app/services/conversation.py`: `thread_id(space, user)`, `run_turn(...) -> str` | [x] |
| 1 | Bot answers with memory | `app/services/google_chat.py`: `_handle_mention` → DM: "I only work in spaces"; empty text: hint; else `run_turn` → `send_message`; failure → "Sorry, something went wrong" | [x] |
| 1 | Bot answers with memory | Tests: fake model + `InMemorySaver`; two turns same (space, user) share history; different user or space doesn't; DM / empty / failure replies; `finalize` truncation | [x] |
| 1 | Bot answers with memory | Manual: @FocalBot in a space, follow-up question uses earlier context; second user gets a fresh conversation | [x] |
| 2 | FIFO per conversation | `app/services/conversation_queue.py`: Redis list + lock + dedup keys; `enqueue`, `drain` | [x] |
| 2 | FIFO per conversation | `app/tasks/conversation.py`: `drain_conversation(space, user, trace_id)` task; `_handle_mention` enqueues + dispatches instead of running inline | [x] |
| 2 | FIFO per conversation | In-drain retries (5 s, 15 s, 60 s), 15 min message expiry, fork-from-pre-turn-checkpoint on retry, clean "sorry" checkpoint on final failure | [x] |
| 2 | FIFO per conversation | Tests (fake Redis): order kept; second drain exits while locked; nothing stranded after release; duplicate message name ignored; retry then success; final failure posts sorry and continues; expired message dropped; retry doesn't duplicate history | [x] |
| 2 | FIFO per conversation | Manual: send 3 quick mentions; replies arrive in order, each referencing the previous | [x] |
| 3 | Conversation log | `app/models/conversation.py`: `Conversation`, `Message`; import both in `app/models/__init__.py`; Alembic migration | [x] |
| 3 | Conversation log | `app/services/conversation_log.py` (defines `ConversationKey` and the `ConversationLog` protocol; its functions take an `AsyncSession`; each function also takes a `ConversationKey` and finds or creates the conversation itself in the same transaction): `record_user_message` (insert-if-absent), `finish_user_message` (upsert: creates the user row if missing, then sets status; the only status writer), `record_reply` (upsert of the one assistant row per user message) | [ ] |
| 3 | Conversation log | Wire into the drain: `app/tasks/conversation.py` defines `TaskConversationLog`, which implements the `ConversationLog` protocol: each method opens `task_session()` and calls the service. `process_item(chat, log, item)` builds the `ConversationKey` and writes the user message before the turn and the reply and final status after it | [ ] |
| 3 | Conversation log | Tests (SQLite): conversation created once per thread; user message + reply recorded; failure → status `failed` + error + apology row; expiry → `expired`; redelivered item doesn't duplicate rows; a DB failure on the first write, or on the last write, never blocks the reply | [ ] |
| 3 | Conversation log | Manual: send two mentions, then `select` from `conversations` and `messages` in psql and read both exchanges; force a failure and see `failed` | [ ] |
| 4 | /reset | `GOOGLE_CHAT_RESET_COMMAND_ID` setting; `_handle_command` routes that id to `enqueue(kind="reset")`; drain deletes the thread and posts "Conversation cleared" | [ ] |
| 4 | /reset | Tests: reset after messages clears only that (space, user); other user/space intact; queued-before-reset messages answered first; unknown command id still just logs | [ ] |
| 4 | /reset | Manual: register `/reset` in the Chat console, run it, follow-up has no memory | [ ] |
| 5 | Knowledge tool | `app/agent/tools/knowledge.py`: `search_knowledge(query)` returns a fixed string; space read from runtime context; wired into the agent | [ ] |
| 5 | Knowledge tool | Tests: scripted tool call → tool runs with the space from context → answer uses its output; tool not exposed a `space` argument | [ ] |
| 6 | Summarization | `SummarizationMiddleware(model=get_model("summary"), trigger=("tokens", 8000), keep=("messages", 20))` on the agent | [ ] |
| 6 | Summarization | Tests: below threshold no summary call; above → history replaced by summary + last 20, persisted in the checkpoint | [ ] |
| 7 | Docs | `docs/wiki/conversation.md` (flow, queue, conversation log, reset, settings, troubleshooting); `docs/wiki/google-bot.md` "What the worker does" updated; `docs/wiki/index.md` line | [ ] |

## Context

FocalBot (the Google Chat app) receives @mentions and slash commands (GH-2, GH-1), acks "Got it", and the worker only logs them. GH-6 adds a way for the worker to post into a space as the app.

This ticket turns a mention into a conversation. An agent built with LangGraph answers in the space where it was mentioned. It remembers what that user said in that space, and it can call tools before replying. RAG retrieval does not exist yet (ingestion and embeddings do, search does not), so the knowledge tool is a stub with the real interface.

Decisions settled in the design discussion:
- Conversation per (space, user). Spaces only, no DMs, no thread-level conversations.
- Custom graph with state, because RAG and other steps will be added as nodes.
- Summarization once history passes 8,000 tokens.
- A strict FIFO per conversation with retries that keep order, a 15 minute TTL, and failed messages dropped with an apology.
- `/reset` as a slash command.
- OpenRouter for models, with different models per kind of work.
- "Got it" ack stays.

## Decisions

1. **LangGraph checkpointer is the agent's memory, not the record.** `AsyncPostgresSaver` (`langgraph-checkpoint-postgres`) keeps the full graph state, messages included, keyed by `thread_id`. It does history, forking and deletion (`adelete_thread`) for the agent. It brings psycopg 3 alongside asyncpg; the conninfo is derived from `DATABASE_URL` (`postgresql+asyncpg://` → `postgresql://`). The checkpoint stores messages as serialized blobs and is rewritten on purpose (`/reset` deletes the thread, summarization replaces old messages, retries fork branches), so it cannot be read as a history. The readable record is the conversation log (Decision 19).
2. **Checkpointer tables via a CLI command, not Alembic.** `AsyncPostgresSaver.setup()` owns and migrates its own tables (it tracks its own versions). Mirroring them in Alembic would fight it. `uv run cli setup-checkpointer` calls `setup()`, which is idempotent. `make migrate` runs it after `alembic upgrade head`, so one command still prepares the database.
3. **Thread id = `gchat:{space}:{user}`.** For example `gchat:spaces/AAA:users/123`. It uses `sender.name` (stable) rather than email (can change, and is optional in the payload). Messages without a sender are ignored.
4. **Spaces only.** `space.type == "DM"` (the DM fixture has `type: DM`, `spaceType: DIRECT_MESSAGE`) gets one reply, "I only work in spaces. Mention me in a space.", and no agent run. A mention with no text after `@FocalBot` gets "Ask me something after the mention." and no agent run.
5. **Graph shape: custom `StateGraph` wrapping a `create_agent` subgraph.**

        START → agent → finalize → END
                  └─ create_agent(model, tools, system_prompt, middleware=[Summarization])

   - The outer graph owns the flow, so future fixed steps (retrieve before the agent, guardrails, routing) become nodes here.
   - The agent loop (model ↔ tools) is LangChain v1 `create_agent`, compiled and added as the `agent` node. That is what lets `SummarizationMiddleware` work, since middleware attaches to `create_agent`, not to a hand-written graph.
   - The subgraph shares the `messages` key and inherits the parent's checkpointer.
   - `finalize` reads the last AI message, trims it to 8000 chars (with "… (truncated)") and stores it in `state["reply"]`. Chat formatting rules live in the system prompt.
6. **State.**

   ```python
   class ConversationState(TypedDict):
       messages: Annotated[list[AnyMessage], add_messages]
       reply: str
   ```

   Per-turn facts that the LLM must not control (space, user id, display name) travel as **runtime context** (`context=ConversationContext(...)`), not as state the model can write. Tools read the space from there.
7. **Model factory by role.** `get_model(role: Literal["chat", "summary"]) -> BaseChatModel` builds `ChatOpenAI(model=…, api_key=LLM_API_KEY, base_url=LLM_BASE_URL, timeout=LLM_TIMEOUT_SECONDS, max_retries=0)`, built per call, not cached: each Celery task runs in its own event loop, and a cached model (or langchain_openai's cached httpx client) stays bound to the first loop and fails with "Event loop is closed".
   - Graph code asks for a role and never names a model, so swapping a model is an env change, and tests patch one function.
   - `LLM_BASE_URL` defaults to `https://openrouter.ai/api/v1`. `LLM_SUMMARY_MODEL` empty means "same as chat".
   - The key is separate from `EMBEDDING_API_KEY` (it can be the same value) so the two can be rotated or billed apart.
   - Empty `LLM_API_KEY` or `LLM_CHAT_MODEL` raises a clear `ConversationError` on the first turn; the user gets the apology.
   - `max_retries=0` because retries belong to the drain (Decision 10), as with the embedder.
8. **Turn limits.** `recursion_limit=12` per turn caps the tool loop. `LLM_TIMEOUT_SECONDS` (default 60) bounds each LLM call. Hitting either is a failure (Decision 10).
9. **Per-conversation FIFO queue in Redis.** Keys (all under `REDIS_URL`, prefix `chat:`):

   | Key | Type | Purpose |
   |-----|------|---------|
   | `chat:q:{space}:{user}` | list | Pending items, JSON `{kind: "message" \| "reset", message_name, text, display_name, trace_id, enqueued_at}` |
   | `chat:lock:{space}:{user}` | string, `SET NX EX 900` | Only one drain per conversation; value is a random token |
   | `chat:seen:{message_name}` | string, `SET NX EX 86400` | Dedup: Celery is at-least-once (`acks_late`) and Google retries events |

   - **Mention flow.** `_handle_mention` calls `enqueue` (skipped if `seen` already exists), then dispatches `drain_conversation(space, user, trace_id)`.
   - **Drain loop.** Take the lock. If that fails, exit, because the holder will reach the item. While the list is non-empty: refresh the lock's TTL to 900 s, peek the head (`LINDEX 0`), process it, then `LPOP`. Then release the lock (compare-and-delete via a Lua script, so it never deletes another worker's lock).
   - **Avoiding a stranded item.** After releasing, check `LLEN` again. If it is non-zero, loop and try the lock again. This closes the race where an item is pushed between the last pop and the release.
   - **Peek-then-pop.** A crashed worker leaves the item at the head for the next drain (at-least-once). The cost is a possible duplicate reply after a crash, and that is accepted.
   - **Expired lock.** The lock TTL (15 min) is the crash backstop: a dead worker's lock expires and the next mention's drain takes over.
   - Redis client: a `coredis` client opened per task (no shared lifespan in Celery), like `task_session`.
10. **Retries inside the drain, so order holds.** A failed turn is retried in the same drain (`asyncio.sleep` 5 s, 15 s, 60 s) while holding the lock. Celery's `retry` would put the task back on the queue and let the next message overtake.
    - Retryable: `openai.APIConnectionError`, `APITimeoutError`, `RateLimitError`, `InternalServerError`, `GoogleChatError` with status ≥ 500 or `None`.
    - Anything else fails at once.
    - **Final failure** (retries spent, a non-retryable error, or the item is older than 15 min when it reaches the head): post "Sorry, something went wrong. Please try again." (best effort; if even that fails, log it), pop the item, continue with the next one.
11. **Retries don't corrupt history.** A failed run can leave half a turn in the checkpoint, for example a human message plus an AI tool call with no tool result, and the next LLM call would reject that.
    - Before a turn, `run_turn` reads the thread's current `checkpoint_id`.
    - Each retry invokes from that checkpoint (`configurable.checkpoint_id`), which forks a fresh branch. The new branch becomes the thread's latest.
    - On final failure, `aupdate_state` from the same pre-turn checkpoint writes `[HumanMessage(text), AIMessage(sorry)]`, so the latest state is clean and matches what the user saw.
    - The `HumanMessage` id is the Chat message name, so `add_messages` replaces instead of duplicating if it is ever re-applied.
12. **Reply delivery.** After a successful turn, the drain posts `state["reply"]` with `google_chat.send_message` (GH-6) to the space, then pops. Posting is part of "processing", so a Chat 5xx retries the post. To avoid a second LLM call, the reply is posted from the stored state rather than by re-running the graph. The retry loop wraps "run turn" and "post" separately.
13. **`/reset` goes through the queue.** `GOOGLE_CHAT_RESET_COMMAND_ID` (int; 0 = not configured) is matched against `app_command_metadata.app_command_id` (route on the ID, as planned in 006).
    - The command enqueues `{kind: "reset"}` for (space, sender) and dispatches the drain.
    - The drain runs `checkpointer.adelete_thread(thread_id)` and posts "Conversation cleared."
    - Going through the FIFO avoids racing a turn that is mid-run. Messages sent before `/reset` are answered first, then cleared, which matches the order the user typed them.
    - Other command ids (`/add-knowledge`) keep logging as today.
14. **Stub knowledge tool, real interface.** `search_knowledge(query: str) -> str` returns a fixed string ("No knowledge base is connected yet."). It reads the space from runtime context (`ToolRuntime[ConversationContext]`), so the LLM never chooses whose knowledge to search. This matches "a collection will be a space": real RAG later swaps the body for a vector search filtered by the space's collection.
15. **Summarization.**
    - `SummarizationMiddleware(model=get_model("summary"), trigger=("tokens", 8000), keep=("messages", 20))`.
    - The summary replaces older messages in the checkpointed state, so the stored history stays bounded too, not just the prompt.
    - The middleware keeps AI tool-call / tool-result pairs together when cutting.
    - Thresholds are constants in `graph.py`, not env vars, until there is a reason to tune them per environment.
16. **System prompt.** Covers:
    - Who the bot is (FocalBot) and the user's display name.
    - That it is in a shared space, and that other people may read replies.
    - Chat formatting: `*bold*`, `_italic_`, no Markdown headings or tables.
    - Being concise.
    - Using `search_knowledge` for questions about the team's knowledge.

    It lives in `app/agent/prompts.py`.
17. **Ack unchanged.** The webhook still replies "Got it" synchronously. "Thinking…" then edit-in-place is a later change on the GH-6 client.
18. **Worker concurrency note.** `make worker` uses `--pool=solo` (one task at a time), so locally the drain also blocks other chat events and crawls while a turn runs. That's correct but slow. Production should run with more than one worker process; the queue and lock are what make that safe.
19. **Conversation log: readable record in our own tables.** Two tables, separate from the checkpointer, written by the drain. They are the record; the checkpointer stays the agent's memory (Decision 1). They are channel-neutral, so a web interface can write to them later.

    | Table | Columns |
    |-------|---------|
    | `conversations` | `id`, `channel` (`google_chat` \| `web`), `thread_id` (LangGraph thread id; unique with `channel`), `space` (nullable), `external_user` (nullable; the Chat `users/…` id), `display_name`, `user_id` (nullable FK to `users`, for a future web login), `created_at`, `last_message_at` |
    | `messages` | `id`, `conversation_id` (FK), `role` (`user` \| `assistant`), `content`, `external_id` (nullable; unique per conversation: the Chat message name on user rows, `{message_name}#reply` on assistant rows), `chat_message_name` (nullable; the name of the reply Chat posted), `status` (`pending` \| `answered` \| `failed` \| `expired` on user rows; null on assistant rows), `error` (nullable), `created_at` |

    - **API.** Every function takes a `ConversationKey` (a frozen dataclass in `conversation_log.py`: `channel`, `thread_id`, `space`, `external_user`, `display_name`; `process_item` builds it from the queue item with `channel="google_chat"`, `thread_id(space, user)`, and the item's `display_name`) and finds or creates the conversation itself, in the same session and transaction as its write. There is no separate "get or create" step for the caller, and no write depends on an earlier one having succeeded.
    - **Write order.** Before the turn: `record_user_message(db, key, message_name, text)` inserts the user row as `pending`. After it: `record_reply(db, key, message_name, text, chat_message_name)` writes the assistant row (the reply, or the apology on failure or expiry), and `finish_user_message(db, key, message_name, text, status, error)` sets the user row to `answered`, `failed` (with the error type and message) or `expired`. `finish_user_message` is an upsert: if the first write failed, or the item expired before it was ever logged, it creates the user row (from `text`) and then sets the status, so the outcome is never lost. An expired item gets the same treatment, with the apology as the assistant row.
    - **Redelivery (peek-then-pop, Decision 9).** `record_user_message` is insert-if-absent and never resets an existing status to `pending`. `finish_user_message` is the only writer of `status`, and the latest outcome wins, because it is what the user last saw. `record_reply` keys the assistant row on `{message_name}#reply`, so a rerun updates that row's content and `chat_message_name` instead of adding a second reply row. The Chat message name of a rerun's reply differs, which is why it is stored in its own column and not in `external_id`.
    - **Sessions.** A DB session is never held across the LLM call or the Chat post. Services take an `AsyncSession` and never open one (`docs/architecture/index.md`), so the entry point supplies the log. `ConversationLog` is a `Protocol` in `app/services/conversation_log.py` (methods without a session: `record_user_message(key, message_name, text)`, `record_reply(...)`, `finish_user_message(...)`), which is what `drain` and `process_item` are typed against. `TaskConversationLog`, in `app/tasks/conversation.py`, implements it: each method opens `task_session()` for one write and calls `conversation_log.*(db, ...)`. `process_item` takes the log and never sees a session. Tests pass a fake or one backed by the SQLite session.
    - **Best effort.** A failing log write is logged and never blocks the reply or the pop: the bot's answer matters more than its record. Because every function finds or creates the conversation and the user row itself, a failed first write costs nothing but a short window in which the row is missing.
    - **Reset.** `/reset` clears the agent's memory only. The conversation row and its messages stay.
    - **Thread id.** For Google Chat `thread_id` stays `gchat:{space}:{user}`, so nothing about existing checkpoints changes. A web channel would use its own scheme.
    - **Out of scope here.** Model name, token counts and latency per reply (add as columns later), a UI to browse the log, and a retention policy.

## Code sketches

`app/agent/models.py`

```python
Role = Literal["chat", "summary"]


def get_model(role: Role) -> BaseChatModel:
    model = settings.llm_summary_model if role == "summary" else ""
    model = model or settings.llm_chat_model
    if not settings.llm_api_key or not model:
        raise ConversationError("LLM_API_KEY / LLM_CHAT_MODEL are not set")
    return ChatOpenAI(
        model=model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout_seconds,
        max_retries=0,  # the drain owns retries
    )
```

`app/agent/graph.py`

```python
@dataclass(frozen=True)
class ConversationContext:
    space: str
    user: str
    display_name: str


def build_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    agent = create_agent(
        model=get_model("chat"),
        tools=TOOLS,
        system_prompt=system_prompt,  # dynamic: reads display_name from context
        context_schema=ConversationContext,
        middleware=[
            SummarizationMiddleware(
                model=get_model("summary"), trigger=("tokens", 8000), keep=("messages", 20)
            )
        ],
    )
    graph = StateGraph(ConversationState, context_schema=ConversationContext)
    graph.add_node("agent", agent)
    graph.add_node("finalize", finalize)
    graph.add_edge(START, "agent")
    graph.add_edge("agent", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=checkpointer)


def finalize(state: ConversationState) -> dict:
    text = state["messages"][-1].text
    if len(text) > MAX_REPLY_CHARS:
        text = text[: MAX_REPLY_CHARS - 15] + "… (truncated)"
    return {"reply": text}
```

`app/services/conversation.py`

```python
def thread_id(space: str, user: str) -> str:
    return f"gchat:{space}:{user}"


async def run_turn(
    graph, ctx: ConversationContext, message_name: str, text: str, from_checkpoint: str | None
) -> str:
    config = {
        "configurable": {"thread_id": thread_id(ctx.space, ctx.user)},
        "recursion_limit": RECURSION_LIMIT,
    }
    if from_checkpoint:
        config["configurable"]["checkpoint_id"] = from_checkpoint
    state = await graph.ainvoke(
        {"messages": [HumanMessage(text, id=message_name)]}, config, context=ctx
    )
    return state["reply"]


async def current_checkpoint(graph, ctx) -> str | None: ...
async def record_failure(
    graph, ctx, message_name, text, from_checkpoint
) -> None: ...  # aupdate_state
async def reset(checkpointer, space: str, user: str) -> None:
    await checkpointer.adelete_thread(thread_id(space, user))
```

`app/services/conversation_queue.py` (shape)

```python
async def enqueue(redis, item: QueueItem) -> bool:
    """False if this Chat message was already queued (dedup)."""
    if item.message_name and not await redis.set(
        f"chat:seen:{item.message_name}", "1", nx=True, ex=86400
    ):
        return False
    await redis.rpush(queue_key(item.space, item.user), [item.model_dump_json()])
    return True


async def drain(
    redis, space: str, user: str, process: Callable[[QueueItem], Awaitable[None]]
) -> None:
    while True:
        token = uuid4().hex
        if not await redis.set(lock_key(space, user), token, nx=True, ex=LOCK_TTL):
            return  # another drain owns this conversation
        try:
            while (raw := await redis.lindex(queue_key(space, user), 0)) is not None:
                await redis.expire(lock_key(space, user), LOCK_TTL)
                await process(
                    QueueItem.model_validate_json(raw)
                )  # never raises: handles its own failure
                await redis.lpop(queue_key(space, user))
        finally:
            await release(redis, lock_key(space, user), token)  # Lua compare-and-delete
        if not await redis.llen(queue_key(space, user)):
            return
```

`app/tasks/conversation.py`

```python
class TaskConversationLog:
    """Slice 3: each method opens a short session, so none is held across the LLM or Chat call."""

    async def record_user_message(self, key, message_name, text) -> None:
        async with task_session() as db:
            await conversation_log.record_user_message(db, key, message_name, text)

    # record_reply and finish_user_message the same way


@celery_app.task
def drain_conversation(space: str, user: str, trace_id: str) -> None:
    with logger.contextualize(trace_id=trace_id, job="drain_conversation"):
        # SYNC-EXCEPTION: Celery task bodies are sync; asyncio.run drives the async work
        asyncio.run(conversation_service.drain(space, user, TaskConversationLog()))
```

Until slice 3 lands, the task calls `conversation_service.drain(space, user)` with no log.

`app/services/conversation.drain` opens the per-task resources (Redis client, httpx + `GoogleChatClient`) and passes a `process` callback that does the turn, retry, post, and failure handling. It opens the graph (and so the checkpointer connection) per item inside the error handling, so a missing LLM key or an unreachable database still ends in the apology. From slice 3 the task also passes a `ConversationLog` (Decision 19): `conversation_service.drain(space, user, log)`.

`.env.example` (additions)

```
# Conversational agent: OpenAI-compatible chat API (OpenRouter by default)
LLM_BASE_URL=https://openrouter.ai/api/v1
# Empty = every turn fails with "Sorry, something went wrong"
LLM_API_KEY=
# OpenRouter model id for replies (e.g. provider/model-name)
LLM_CHAT_MODEL=
# Model for conversation summaries; empty = same as LLM_CHAT_MODEL
LLM_SUMMARY_MODEL=
LLM_TIMEOUT_SECONDS=60

# Command ID registered for /reset in the Chat API console; 0 = not configured
GOOGLE_CHAT_RESET_COMMAND_ID=0
```

## Files to create/modify

| File | Slice | Purpose |
|------|-------|---------|
| `pyproject.toml`, `uv.lock` | 1 | New dependencies |
| `app/core/config.py`, `.env.example` | 1, 4 | LLM settings (1); reset command id (4) |
| `app/agent/__init__.py` | 1 | Package |
| `app/agent/models.py` | 1 | `get_model(role)` |
| `app/agent/state.py` | 1 | `ConversationState`, `ConversationContext` |
| `app/agent/prompts.py` | 1 | System prompt |
| `app/agent/graph.py` | 1, 5, 6 | `build_graph`, `finalize` (1); tools (5); middleware (6) |
| `app/agent/checkpointer.py` | 1 | `open_checkpointer()` async context manager |
| `app/agent/tools/__init__.py`, `tools/knowledge.py` | 5 | `TOOLS`, `search_knowledge` |
| `app/services/conversation.py` | 1, 2, 3, 4 | `run_turn` (1); drain + process callback, retries, failure checkpoint (2); log writes in `process_item` (3); reset (4) |
| `app/services/conversation_queue.py` | 2 | Redis queue, lock, dedup |
| `app/models/conversation.py`, `app/models/__init__.py`, `alembic/versions/` | 3 | `Conversation`, `Message`; migration |
| `app/services/conversation_log.py` | 3 | `ConversationKey`, the `ConversationLog` protocol, and the functions that record user message, reply and final status; each call finds or creates the conversation |
| `tests/unit/test_conversation_log.py` | 3 | Log service and its wiring in `process_item` |
| `app/services/google_chat.py` | 1, 2, 4 | Mention → conversation (1); enqueue + dispatch (2); reset command (4) |
| `app/tasks/conversation.py`, `app/core/celery_app.py` | 2, 3 | `drain_conversation` task; add to `include` (2); `TaskConversationLog` (implements the protocol, opens `task_session()` per write) (3) |
| `app/cli/__main__.py`, `Makefile` | 1 | `setup-checkpointer`; `make migrate` runs it |
| `tests/agent_helpers.py` | 1 | Fake model factory (`GenericFakeChatModel` with scripted messages / tool calls), fake Chat client recorder |
| `tests/unit/test_conversation_graph.py` | 1, 5, 6 | Graph, memory, tool (5), summarization (6) |
| `tests/unit/test_conversation_queue.py` | 2 | Queue / lock / dedup / retry / expiry |
| `tests/unit/test_google_chat_task.py` | 1, 2, 4 | Handler routing (DM, empty, mention, reset) |
| `tests/conftest.py` | 2 | Stub `app.services.google_chat.dispatch` in the `dispatched` fixture |
| `docs/wiki/conversation.md`, `docs/wiki/google-bot.md`, `docs/wiki/index.md` | 7 | Docs |

## Testing plan

No test calls an LLM, Google or a real Redis.
- `get_model` is patched to return `GenericFakeChatModel` (or a small `BaseChatModel` subclass that supports `bind_tools` and returns scripted `AIMessage`s, including `tool_calls`).
- The checkpointer is `InMemorySaver`.
- Chat posting uses a recorder in place of `send_message`.
- Redis uses `fakeredis` if it works with the coredis calls used. Otherwise the queue gets a small in-memory fake behind a protocol covering `set nx ex`, `rpush`, `lindex`, `lpop`, `llen`, `expire` and the release script.

The checkpointer's Postgres behaviour is LangGraph's own and is not re-tested; `setup-checkpointer` is covered by the manual step.

**Slice 1**
- Turn 1 "my name is Ana" and turn 2 "what's my name" on the same (space, user): the second model call receives both earlier messages.
- Same user in another space, or another user in the same space: a fresh history.
- DM fixture → "I only work in spaces" posted, model never called.
- Mention with blank text → hint posted, model never called.
- Model raises → apology posted, nothing else.
- `finalize` truncates a 9000-char reply to ≤ 8000 with the suffix.
- `get_model` with an empty key → `ConversationError`.

**Slice 2**
- Three enqueued items are processed in order.
- A second `drain` while the lock is held returns at once.
- An item pushed after the last pop but before release is still processed (loop re-check).
- Enqueuing the same message name twice → one item.
- Retryable error then success: one reply, history has exactly one human and one AI message for that turn (fork worked).
- Retries spent → apology posted, the checkpoint holds human + apology, the next item still runs with clean history.
- An item older than 15 min → apology, no model call.
- A non-retryable error → no retry.
- Lock release never deletes a lock with another token.

**Slice 3**
- The first message creates one `conversations` row; the next one in the same thread reuses it.
- A turn leaves a `user` message (status `answered`) and an `assistant` message with the reply.
- A failed turn leaves the user message `failed` with the error text, and an assistant row holding the apology.
- An expired item that was never logged gets its user row created and marked `expired`, plus an assistant row holding the apology.
- The same item processed twice (a crash after the reply, before the pop) leaves one user row and one assistant row; the assistant row holds the latest reply and its Chat message name, and the user status is the latest outcome.
- Redelivery never resets an `answered` user row back to `pending`.
- If the first log write raises, the reply is still posted, the item is still popped, and the later writes still produce the conversation, the user row (created by `finish_user_message`) with its final status, and the assistant row.
- If the last log write raises, the reply is still posted and the item is still popped.
- The conversation `thread_id` is `gchat:{space}:{user}`, matching the checkpointer's.

**Slice 4**
- Reset command id → reset item enqueued.
- Draining [msg, reset, msg] → reply, "Conversation cleared.", then the third turn sees no history.
- Another (space, user) thread is untouched.
- Command id 1 (`/add-knowledge`) → logs only.
- `GOOGLE_CHAT_RESET_COMMAND_ID=0` → no command treated as reset.

**Slice 5**
- The fake model calls `search_knowledge("x")`; the tool output reaches the next model call; the tool saw `space` from context.
- The tool's schema has only `query`.

**Slice 6**
- With a tiny token trigger in the test, history over the trigger → the summary model is called once, and the state's messages are the summary plus the last N.
- Under the trigger → the summary model is not called.

## Verification

- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check .`
- `make migrate` on a fresh database creates the Alembic tables and the checkpoint tables (`checkpoints`, `checkpoint_writes`, `checkpoint_blobs`, `checkpoint_migrations`); running it again is a no-op.
- Manual, with `make dev` + `make worker` behind the tunnel and GH-6 credentials set:
  1. @FocalBot "my name is Ana", then "what is my name?" → the bot answers with Ana.
  2. A second account in the same space asks "what is my name?" → the bot doesn't know.
  3. Three quick mentions → three replies in order.
  4. `/reset`, then "what is my name?" → the bot doesn't know. The other user's conversation still works.
  5. DM the bot → "I only work in spaces".
  6. Set `LLM_API_KEY` to garbage and restart the worker → the apology is posted, and the next message after fixing the key works with clean history.
  7. Ask a knowledge question → the worker log shows the `search_knowledge` call.
  8. In psql, `select * from conversations` and `select role, content, status from messages order by id` show the exchanges from steps 1 to 3 in order; after `/reset` the rows are still there. The garbage-key run in step 6 shows a `failed` user message with the error text.
