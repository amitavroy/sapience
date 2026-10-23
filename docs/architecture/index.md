# Architecture

## Layers

### Persistence lives in services

Routes, Celery tasks, dependencies and the CLI are entry points. They do not persist data. They contain no `db.add`, `db.commit`, `db.execute`, `db.get` or `db.delete`, and no queries. All reads and writes of our own tables, and the transaction around them, belong in `app/services/`.

- **Entry points are thin.** They parse input, provide a session, call a service, map the result to a response or a log line, and handle retries or HTTP status codes. Business rules and persistence stay out of them.
- **The entry point owns the session's lifetime; the service owns the transaction.** Routes get the session from `Depends(get_db)`. Tasks and CLI commands open one with `task_session()` (or `async_session_factory()` in the CLI) and dispose of it when done. They pass it to a service, which commits (or rolls back) and reports the outcome as a return value or a domain exception.
- **One service function per operation.** Services take an `AsyncSession` as their first argument and never open one themselves, so routes, tasks and the CLI call the same function. Do not write a `_for_task` twin of a service function.
- **Hold a session only while you need it.** A task that does slow network work (crawling, LLM calls) opens its session after that work, not before, so no database connection sits idle during it.
- **Reviewers:** a query or write in a route, task or CLI command is a defect; move it into a service. A service that opens its own session is also a defect, unless it is a standalone helper with no caller that can provide one.

## Async first

This project is async by default for **I/O-bound** work (database, Redis, outbound HTTP, LLM APIs). Use async wherever the stack allows it.

The goal is to never block the event loop. The event loop is one worker serving many requests: `await` lets it serve others while one request waits on I/O. A blocking or CPU-heavy call inside an `async def` stalls every other request, including `/health`.

### Rules

1. **Handlers and dependencies are `async def`.** Route handlers, `Depends` callables, middleware and lifespan hooks are all async.
2. **Database access is async.** SQLAlchemy `AsyncEngine` / `AsyncSession` with an async driver (`asyncpg` for Postgres, `aiosqlite` in tests). Alembic runs through an async `env.py`.
3. **Network and I/O use async clients.** Redis uses `coredis`; outbound HTTP uses `httpx.AsyncClient`. Blocking clients (e.g. `requests`) must never be called from `async def` code.
4. **Tests are async.** `pytest-asyncio` (`asyncio_mode = "auto"`) with `httpx.AsyncClient` on `ASGITransport`.
5. **Never block the event loop.** No blocking calls (`time.sleep`, sync file or network I/O) and no CPU-heavy work inside `async def`.

### Outbound API calls (OpenAI, OpenRouter, other services)

Calls to external APIs are I/O-bound: the server waits while the remote side does the work. They must be async.

- **Client:** `openai.AsyncOpenAI`. OpenRouter is OpenAI-compatible, so use the same client with `base_url="https://openrouter.ai/api/v1"`. For other APIs use `httpx.AsyncClient`. The sync `OpenAI` client must not be used inside `async def`.
- **One shared client:** create it in the app lifespan and close it on shutdown. Do not build a client per request.
- **Timeouts and retries:** always set an explicit timeout and a retry policy. LLM calls can take tens of seconds.
- **Concurrency:** run independent calls with `asyncio.gather`, bounded by an `asyncio.Semaphore` to respect provider rate limits.
- **Streaming:** return `StreamingResponse` from an async generator so tokens reach the client as they arrive.
- **Very long jobs:** if a call can run for minutes, use a background task or queue with a status endpoint instead of holding the HTTP request open.

### CPU-bound work

Async does not speed up CPU work. CPU-bound functions (local embeddings, PDF parsing, image processing, heavy post-processing) are normal sync functions, and that is fine. The rule is about **where they run**: never directly inside an `async def`.

- **Process pool** (`loop.run_in_executor` with a `ProcessPoolExecutor`) or a **separate worker** (Celery, ARQ): use this for real CPU work. It runs on another core and leaves the loop free.
- **Thread pool** (`asyncio.to_thread`, `run_in_threadpool`, or a plain `def` route): suited to blocking I/O from a library with no async API. It helps little for pure CPU work because of Python's GIL.

### When async isn't possible

Some things have no async option: a sync-only library, a blocking SDK, CPU-bound work. When that happens:

1. **Flag it.** Say so in the PR/ticket, and in the code with a comment on the line:

   ```python
   # SYNC-EXCEPTION: <library/operation> has no async API; <how it is isolated>
   ```

2. **Isolate it.** Keep it off the event loop using the options above.
3. **Record it.** Add a row to the table below.

### Sync exceptions

| Where | What | Why it can't be async | Isolation |
|-------|------|-----------------------|-----------|
| `alembic/env.py` | Migrations run via `connection.run_sync(...)` | Alembic's migration context is sync | Runs on an async connection; only used at deploy/CLI time, not serving requests |
| `app/cli/__main__.py` | Typer commands are sync entry points | Typer has no native async support | Each command calls `asyncio.run(...)` for async work |
| `app/core/security.py` | Argon2 password hashing and verification | CPU-bound; pwdlib has no async API | Called through `asyncio.to_thread`, so the event loop stays free |
| `app/services/web_extractor.py` | HTML parsing and block extraction with selectolax | CPU-bound; selectolax has no async API | Called through `asyncio.to_thread`; runs in the Celery worker |
| `app/services/chunking/` | Splitting an extracted document into chunks | CPU-bound pure-Python work; no I/O to await | Called through `asyncio.to_thread`; runs in the Celery worker |

### Known risks

- **Test DB differs from the real DB.** Tests use SQLite via `aiosqlite`; development uses Postgres with pgvector. SQLite has no vector type or other Postgres-specific features, so models or queries that rely on them cannot be exercised under the default test DB. Flag such tests and cover them separately.
  - Example: `chunks.embedding` is pgvector `vector(1536)` on Postgres but plain JSON under SQLite (`with_variant`). Model tests prove storage, constraints and cascades only; vector search (`<=>`, the HNSW index) is not covered by the test suite and was verified by hand against Postgres. Cover it with a Postgres-backed test when retrieval is built.

### Notes for reviewers and for Claude

- A blocking call or CPU-heavy work inside `async def`, without a `SYNC-EXCEPTION` flag and isolation, is a defect; raise it.
- A plain `def` route is **not** a defect: FastAPI runs it in a threadpool, which is an accepted way to handle blocking I/O. Flag it with `SYNC-EXCEPTION` if it exists because no async API was available.
- If a task would need a sync approach, stop and flag it before implementing, rather than working around it silently.
