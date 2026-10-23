# Move persistence code from routes, tasks and deps into services (GH-5)

## To-do

Each slice ends in a working, reviewable state. Pause for review after each slice. Slice 1 fixes the auth dependency, slice 2 the welcome task, slice 3 the health check in the route and the CLI, slice 4 the embedding task.

| # | Slice | Step | Done |
|---|-------|------|------|
| 1 | User lookup | `app/services/user.py`: add `get(db, user_id)`; `get_current_user` in `app/core/deps.py` calls it instead of `db.get(User, ...)` | [ ] |
| 1 | User lookup | Tests: `user_service.get` returns the user / `None`; `test_current_user.py` still passes | [ ] |
| 2 | Welcome task | `app/services/user.py`: add `get_for_task(user_id)`, which opens `task_session()` and returns the user or `None` | [ ] |
| 2 | Welcome task | `app/tasks/user.py`: drop `_welcome_user(db, ...)`, `AsyncSession`, `task_session` and `User` imports; the task calls `asyncio.run(user_service.get_for_task(user_id))` and keeps the log lines | [ ] |
| 2 | Welcome task | Tests: rewrite the two welcome tests in `tests/integration/test_jobs.py` against the task, with `user_service.task_session` patched to yield `db_session` | [ ] |
| 3 | Health check | `app/services/health.py` (new): `ping_db(db)` and `ping_db_standalone()`; `app/routers/health.py` calls `ping_db` | [ ] |
| 3 | Health check | CLI `_ping_db` calls `health.ping_db_standalone()` (the CLI keeps `engine.dispose()`); remove the `sqlalchemy.text` imports from the route and the CLI | [ ] |
| 3 | Health check | Tests: `health.ping_db` on the `db_session` fixture; `test_check_db` patches the health function so it needs no database | [ ] |
| 4 | Embedding task | `app/services/embedding/__init__.py`: add `run_for_task(document_id)` (opens `task_session()`, calls `run_embedding` with `get_embedder()`) and `mark_failed(document_id, error)` (opens `task_session()`, sets `FAILED` and the error, commits; no-op if the document is gone) | [ ] |
| 4 | Embedding task | `app/tasks/embedding.py`: `_run` and `_mark_failed` call the two services; drop the `task_session`, `Document` and `DocumentStatus` imports | [ ] |
| 4 | Embedding task | Tests: repoint the `_run` / `_mark_failed` patches in `tests/unit/test_embedding_task.py` if the wrappers go; service tests for `mark_failed` on `db_session` (document found, document missing) | [ ] |
| 5 | Verify | Run the grep from Verification; `make test` and `make format` clean | [ ] |

## Context

The architecture doc now has a "Persistence lives in services" rule (added with GH-4): routes, Celery tasks, dependencies and the CLI contain no `db.add`, `db.commit`, `db.execute`, `db.get`, no queries, and no session or transaction handling. `app/tasks/crawler.py` was already fixed through `ingest.crawl_and_store`. An audit of the rest of `app/` found these remaining places (the embedding task was added by GH-4 and found in a second pass):

| Where | Violation |
|-------|-----------|
| `app/tasks/user.py` | `_welcome_user` calls `db.get(User, user_id)`; the task opens `task_session()` |
| `app/core/deps.py:33` | `get_current_user` calls `db.get(User, user_id)` |
| `app/routers/health.py:11` | `db.execute(text("SELECT 1"))` in a route |
| `app/cli/__main__.py` `_ping_db` | `engine.connect()` and `SELECT 1` in the CLI |
| `app/tasks/embedding.py` | `_run` opens `task_session()`; `_mark_failed` calls `db.get(Document, ...)`, mutates the row and `db.commit()`s |

Clean, no change: `app/routers/auth.py`, `app/routers/user.py`, `app/routers/ingest.py`, `app/tasks/crawler.py`, `app/tasks/google_chat.py`, the middleware.

## Decisions

1. **Services own the database work; routes, tasks and deps only call them.** This is the rule from the architecture doc, applied to the five places above.
2. **Task-facing services open their own session** with `task_session()`, because a Celery task has no request scope. It is the same pattern as `ingest.crawl_and_store`. `user_service.get_for_task(user_id)` returns the user or `None`; the task keeps the "not found" warning and the welcome log line, with the messages unchanged.
3. **`user_service.get(db, user_id)` is shared** by `get_current_user` and `get_for_task`. It is the one place that loads a user by id.
4. **`get_db` stays in `app/core/deps.py`.** It is session provisioning for `Depends`, not persistence logic. The doc already says route services take the request's session.
5. **The CLI keeps opening its own sessions** (`async_session_factory()` in `_seed_user`, `_create_collection`, `_collection_exists`) and disposing the engine. The rule text allows this, and wrapping it would add three thin functions for little gain.
6. **One health service for the route and the CLI.** `ping_db(db)` runs `SELECT 1` on a given session (the route passes the request session). `ping_db_standalone()` opens its own connection from `engine` for the CLI; the CLI still calls `engine.dispose()`.
7. **Embedding task follows decision 2.** `embedding_service.run_for_task` and `mark_failed` open their own session, like `get_for_task`. The retry logic (`RETRY_DELAYS`, `self.retry`) stays in the task, since it is task control flow, not persistence.
8. **Out of scope:** the strict reading of the CLI rule (session-owning wrappers for every CLI command), and any change to `get_db` or `app/main.py` lifespan disposal.

## Code

`app/services/user.py` (additions):

```python
async def get(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)


async def get_for_task(user_id: int) -> User | None:
    """For Celery tasks, which have no request-scoped session."""
    async with task_session() as db:
        return await get(db, user_id)
```

`app/core/deps.py` (change):

```python
user = await user_service.get(db, user_id) if user_id is not None else None
```

`app/tasks/user.py`:

```python
@celery_app.task
def welcome_user(user_id: int) -> None:
    # SYNC-EXCEPTION: Celery task bodies are sync; asyncio.run drives the async work
    user = asyncio.run(user_service.get_for_task(user_id))
    if user is None:  # deleted before the job ran; nothing to do
        logger.warning(f"welcome_user: user {user_id} not found")
        return
    logger.info(f"welcome {user.email}")  # stub: send the welcome mail here
```

`app/services/health.py` (new):

```python
async def ping_db(db: AsyncSession) -> None:
    await db.execute(text("SELECT 1"))


async def ping_db_standalone() -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
```

`app/routers/health.py`: `await health_service.ping_db(db)` in place of the `db.execute(...)` call.

`app/cli/__main__.py`: `_ping_db` becomes `await health_service.ping_db_standalone()` followed by `await engine.dispose()`.

`app/services/embedding/__init__.py` (additions):

```python
async def run_for_task(document_id: int) -> None:
    """For Celery tasks, which have no request-scoped session."""
    async with task_session() as db:
        await run_embedding(db, document_id, get_embedder())


async def mark_failed(document_id: int, error: str) -> None:
    async with task_session() as db:
        document = await db.get(Document, document_id)
        if document is not None:
            document.status = DocumentStatus.FAILED
            document.error = error
            await db.commit()
```

`app/tasks/embedding.py`: `asyncio.run(embedding_service.run_for_task(document_id))` and `asyncio.run(embedding_service.mark_failed(document_id, str(exc)))` in place of `_run` / `_mark_failed`.

## Files to create/modify

| File | Slice | Purpose |
|------|-------|---------|
| `app/services/user.py` | 1, 2 | `get`, `get_for_task` |
| `app/core/deps.py` | 1 | `get_current_user` calls `user_service.get` |
| `app/tasks/user.py` | 2 | Task calls the service; no database imports |
| `app/services/health.py` (new) | 3 | `ping_db`, `ping_db_standalone` |
| `app/routers/health.py` | 3 | Calls `ping_db`; no `sqlalchemy` import |
| `app/cli/__main__.py` | 3 | `_ping_db` calls the health service; no `text` import |
| `app/services/embedding/__init__.py` | 4 | `run_for_task`, `mark_failed` |
| `app/tasks/embedding.py` | 4 | Task calls the services; no database imports |
| `tests/unit/test_embedding_task.py` | 4 | Patches point at the service functions |
| `tests/integration/test_embedding_service.py` (new, or the existing embedding service test file) | 4 | `mark_failed` |
| `tests/integration/test_jobs.py` | 2 | Welcome tests against the task, `task_session` patched |
| `tests/integration/test_user_service.py` (new, or an existing user service test file) | 1 | `user_service.get` |
| `tests/integration/test_health_service.py` (new) | 3 | `health.ping_db` |
| `tests/unit/test_cli.py` | 3 | `test_check_db` patches the health function |

## Testing plan

No network, no Redis. DB tests use the `db_session` SQLite fixture.

- `user_service.get`: returns the user for a known id, `None` for an unknown one.
- `get_current_user`: `tests/integration/test_current_user.py` passes unchanged.
- Welcome task: patch `user_service.task_session` to yield `db_session`, as `tests/unit/test_crawler.py` does for `ingest.task_session`. Call `welcome_user` as a plain function. An existing user logs `welcome ann@example.com`; a missing user logs a warning and does not raise. These tests are sync, because the task calls `asyncio.run` itself.
- `health.ping_db`: runs on `db_session` without raising.
- `check-db`: patch `health_service.ping_db_standalone` and assert the output is `database ok`.
- `embedding_service.mark_failed`: sets `FAILED` and the error on an existing document, does nothing for a missing id. Patch `embedding.task_session` to yield `db_session`.
- Embedding task: `tests/unit/test_embedding_task.py` still covers retry and failure paths, with the patch targets updated.
- `/health` tests (`test_health.py`, `test_rate_limit.py`, `test_trace.py`) pass unchanged.

## Verification

- `make test` and `make format` are clean.
- `grep -rnE "db\.(add|commit|execute|get|scalar|delete)|task_session|async_session_factory|select\(|text\(" app/routers app/tasks app/cli` returns nothing, except `async_session_factory` in `app/cli/__main__.py` (allowed by decision 5). For `app/core/deps.py`, grep only `db\.(add|commit|execute|get|scalar|delete)|select\(`, because `get_db` legitimately uses `async_session_factory` (decision 4).
- `uv run cli check-db` prints `database ok` against a running Postgres, and `GET /health` returns 200.
- Register a user through the API with the worker running: the worker logs `welcome <email>`.
