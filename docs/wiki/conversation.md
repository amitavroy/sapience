# Conversation flow

An @mention in a space becomes a conversation with an agent that remembers what that user said in that space. One conversation per (space, user): the same user in another space, or another user in the same space, starts fresh.

    @mention → _handle_mention ── DM → "I only work in spaces. Mention me in a space."
                    │            └─ no text → "Ask me something after the mention."
                    └─ enqueue (Redis) → dispatch drain_conversation → worker
                                                │
                       drain: lock → for each queued item: turn → post reply → pop
                                                │
                       turn: graph (agent → finalize) on the Postgres checkpointer

- The webhook still answers "Got it" at once (see [google-bot.md](google-bot.md)). The real reply is posted later by the worker with `google_chat.send_message`, so the app must be in the space and `GOOGLE_CHAT_CREDENTIALS_FILE` must be set.
- Thread id is `gchat:{space}:{user}`, using `sender.name` (`users/…`), which is stable; email can change and is optional. A mention with no sender is ignored.
- The graph is `START → agent → finalize → END`. `agent` runs a LangChain `create_agent` loop (model ↔ tools) and `finalize` trims the last AI message to 8000 characters into `state["reply"]`. The system prompt (`app/agent/prompts.py`) names the user and sets the Chat formatting rules.
- Who is asking (space, user, display name) travels as runtime context, not as state or tool arguments, so the model cannot choose whose data a tool reads.
- The only tool is `search_knowledge(query)`, a stub that returns "No knowledge base is connected yet." Real retrieval replaces its body later.
- A turn is capped at 12 graph steps (`RECURSION_LIMIT`) and each LLM call at `LLM_TIMEOUT_SECONDS`. Hitting either is a failure.

# Memory and summarization

The LangGraph checkpointer (`AsyncPostgresSaver`, built from `DATABASE_URL`) is the agent's memory. It is rewritten on purpose (reset, summarization, retries), so it is not a readable history; the conversation log below is.

- `SummarizationMiddleware` summarizes once history passes 8000 tokens and keeps the last 20 messages (constants in `app/agent/graph.py`). The summary model is `LLM_SUMMARY_MODEL`, or the chat model when that is empty.
- The `agent` node returns a `RemoveMessage(REMOVE_ALL_MESSAGES)` followed by the agent's final messages. A subgraph's output is merged by the parent's `add_messages`, which never sees the middleware's removals, so without this the checkpoint would keep every summarized message and grow forever.
- The checkpointer tables are owned by LangGraph, not Alembic. `make migrate` runs `alembic upgrade head` and then `uv run cli setup-checkpointer`, which is idempotent.

# Queue: one message at a time per conversation

Replies must come back in the order the user typed them, and a second message must not run while the first is still going.

| Redis key | Type | Purpose |
|-----------|------|---------|
| `chat:q:{space}:{user}` | list | Pending items (message or reset) as JSON |
| `chat:lock:{space}:{user}` | string, 900 s | Only one drain per conversation; value is a random token |
| `chat:seen:{message_name}` | string, 1 day | Dedup: Celery is at-least-once and Google retries events |

- `drain_conversation(space, user, trace_id)` takes the lock; if it cannot, it exits, because the holder will reach the new item. While the list is not empty it processes the head, then pops it. After releasing it checks the length again, so an item pushed between the last pop and the release is not stranded.
- Peek, then pop: a worker that crashes mid-item leaves it at the head for the next drain. The cost is a possible duplicate reply after a crash.
- A dead worker's lock expires after 15 minutes and the next mention takes over.
- A duplicate event (same message name) is not queued twice, but the drain is still dispatched, in case the first delivery died before dispatching.
- `make worker` uses `--pool=solo`, so locally one drain blocks every other task while a turn runs. Production should run more than one worker process; the lock is what makes that safe.

# Failures and retries

A failed turn is retried inside the drain, still holding the lock, so the next message cannot overtake it.

| Failure | Handling |
|---------|----------|
| Connection error, timeout, rate limit, 5xx from the LLM; Chat 5xx or no status | Retry after 5 s, 15 s, 60 s |
| Chat credentials not configured, or anything else | Fail at once |
| Item older than 15 minutes when it reaches the head | Dropped as `expired`, no model call |

- Running the model and posting the reply are retried separately, so a Chat outage does not re-run the LLM.
- Each retry starts from the checkpoint taken before the turn, which forks a clean branch. A half-finished attempt (a tool call with no result) never reaches the next LLM call, and history never holds a turn twice. When the thread was empty, the attempt is deleted instead.
- On final failure the user gets "Sorry, something went wrong. Please try again." (best effort), the checkpoint holds their message plus that apology, and the drain moves on to the next item.
- Empty `LLM_API_KEY` or `LLM_CHAT_MODEL` raises a clear error on the first turn, which ends in the same apology.

# Conversation log

Two tables, separate from the checkpointer, are the readable record. They are channel-neutral (`channel` is `google_chat` or `web`).

| Table | Holds |
|-------|-------|
| `conversations` | `channel`, `thread_id` (unique with channel), `space`, `external_user`, `display_name`, optional `user_id`, `created_at`, `last_message_at` |
| `messages` | `role` (`user` / `assistant`), `content`, `external_id`, `chat_message_name`, `status` (`pending` / `answered` / `failed` / `expired` on user rows), `error` |

- Written by the drain through `TaskConversationLog`, which opens a short session per write, so no database connection is held across an LLM or Chat call.
- Every write finds or creates the conversation itself. A user message is stored `pending` before the turn; afterwards the reply row and the final status are written. The status writer creates the user row if the first write was lost, so the outcome is never lost.
- Redelivery is safe: the user row is insert-if-absent, and the assistant row is keyed on `{message_name}#reply`, so a rerun updates it instead of adding a second one. The Chat name of the rerun's reply is stored in `chat_message_name`.
- A failing log write is logged and skipped. The answer matters more than its record.
- Not recorded yet: model name, token counts, latency, a UI to browse, retention.

# /reset

`/reset` clears the user's memory in that space. It goes through the same queue, so messages sent before it are answered first and it never races a running turn.

- Set `GOOGLE_CHAT_RESET_COMMAND_ID` to the command ID registered for `/reset` in the Chat API console (Configuration → Commands). `0` means not configured and no command is treated as a reset. Other command IDs are only logged.
- The drain deletes the checkpoint thread, deletes the conversation's `messages` rows, posts "Conversation cleared." and records that reply as the single remaining message. The `conversations` row stays. The reset command itself is not logged as a user message.
- Ownership: the item is built from the authenticated event's sender and carries no field naming another user or conversation, whatever the command text says. `clear_messages` also matches `channel`, `thread_id` and `external_user` together, so it cannot delete someone else's rows.
- If either delete fails, the user gets the apology, nothing is recorded as cleared, and they run `/reset` again. Both deletes are idempotent. A reset is not retried inside the drain.

# Settings

| Variable | Default | Meaning |
|----------|---------|---------|
| `LLM_BASE_URL` | `https://openrouter.ai/api/v1` | OpenAI-compatible chat API |
| `LLM_API_KEY` | empty | Empty means every turn fails with the apology. Separate from `EMBEDDING_API_KEY` |
| `LLM_CHAT_MODEL` | empty | Model id for replies; empty means turns fail |
| `LLM_SUMMARY_MODEL` | empty | Model for summaries; empty means the chat model |
| `LLM_TIMEOUT_SECONDS` | 60 | Per LLM call |
| `GOOGLE_CHAT_RESET_COMMAND_ID` | 0 | Command ID of `/reset`; 0 means not configured |

- Models are built per call (`app/agent/models.py`), not cached: each Celery task runs in its own event loop, and a cached client stays bound to the first one and fails with "Event loop is closed". The client has `max_retries=0` because retries belong to the drain.

# Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| "Got it" but no reply ever | Worker not running, or the app is not in the space, or `GOOGLE_CHAT_CREDENTIALS_FILE` is empty (the log shows the post failing) |
| Every message gets the apology | `LLM_API_KEY` or `LLM_CHAT_MODEL` empty or wrong; the worker log has the error type and message |
| Replies arrive in the wrong order, or twice | More than one drain holding a conversation (stale lock after a crash lasts up to 15 minutes), or a worker crashed mid-item |
| Bot has no memory of the last message | A different space or user, a `/reset` in between, or the checkpointer tables are missing: run `uv run cli setup-checkpointer` |
| `/reset` does nothing | `GOOGLE_CHAT_RESET_COMMAND_ID` is 0 or does not match the command's ID in the console |
| `/reset` replies with the apology | One of the two deletes failed; the worker log says which. Run it again |
| A message is missing from `messages` | A log write failed (logged as `conversation log ... failed`); the reply was still sent |

# Tests

No test calls an LLM, Google or Redis. `get_model` is patched with a scripted fake chat model (`tests/agent_helpers.py`), the checkpointer is `InMemorySaver`, Chat posting uses a recorder, and Redis is an in-memory fake. The conversation log runs on SQLite. Not covered: the Postgres checkpointer itself (LangGraph's own, checked by hand with `setup-checkpointer`).
