# Move persistence code from routes, tasks and deps into services (GH-5)

## To-do

Each slice ends in a working, reviewable state. Pause for review after each slice. Slice 1 fixes the auth dependency, slice 2 the welcome task, slice 3 the health check in the route and the CLI, slice 4 the embedding task, slice 5 the crawl task.

| # | Slice | Step | Done |
|---|-------|------|------|
| 1 | User lookup | `app/services/user.py`: add `get(db, user_id)`; `get_current_user` in `app/core/deps.py` calls it instead of `db.get(User, ...)` | [x] |
| 1 | User lookup | Tests: `user_service.get` returns the user / `None`; `test_current_user.py` still passes | [x] |
| 2 | Welcome task | `app/services/user.py`: remove `get_for_task` and its `task_session` import (added earlier, superseded by decision 2) | [x] |
| 2 | Welcome task | `app/tasks/user.py`: drop `_welcome_user(db, ...)`, `AsyncSession` and `User` imports; an async helper opens `task_session()` and calls `user_service.get(db, user_id)`; the task runs it with `asyncio.run` and keeps the log lines. Import `user_service` inside the helper, because `app/services/user.py` imports this module | [x] |
| 2 | Welcome task | Tests: rewrite the two welcome tests in `tests/integration/test_jobs.py` against the task, with `app.tasks.user.task_session` patched to yield `db_session` | [x] |
| 3 | Health check | `app/services/health.py` (new): `ping_db(db)`; `app/routers/health.py` calls it | [x] |
| 3 | Health check | CLI `_ping_db` opens `async_session_factory()` like the other commands and calls `health.ping_db(db)` (the CLI keeps `engine.dispose()`); remove the `sqlalchemy.text` imports from the route and the CLI | [x] |
| 3 | Health check | Tests: `health.ping_db` on the `db_session` fixture; `test_check_db` patches `health.ping_db` and the session factory so it needs no database | [x] |
| 4 | Embedding task | `app/services/embedding/__init__.py`: add `mark_failed(db, document_id, error)` (sets `FAILED` and the error, commits; no-op if the document is gone) | [ ] |
| 4 | Embedding task | `app/tasks/embedding.py`: `_run` opens `task_session()` and calls `run_embedding(db, ...)`; `_mark_failed` opens `task_session()` and calls `embedding_service.mark_failed(db, ...)`; drop the `Document` and `DocumentStatus` imports | [ ] |
| 4 | Embedding task | Tests: service tests for `mark_failed` on `db_session` (document found, document missing); `tests/unit/test_embedding_task.py` still passes | [ ] |
| 5 | Crawl task | `app/services/ingest.py`: remove `crawl_and_store` and its `task_session` import. `app/tasks/crawler.py`: an async helper calls `crawler_service.crawl_page`, then opens `task_session()` and calls `ingest.store_extracted(db, ...)`, returning the same `(outcome, doc, stored)` tuple | [ ] |
| 5 | Crawl task | Tests: repoint the `ingest.crawl_and_store` patches in `tests/unit/test_crawler.py` and `test_cli_crawl.py` (if any) to the new seams | [ ] |
| 6 | Verify | Run the grep from Verification; `make test` and `make format` clean | [ ] |

## Context

The architecture doc's "Persistence lives in services" rule (added with GH-4) originally banned any session handling in tasks, which forced "for task" twins of service functions that open their own session. This ticket changes the rule: the **entry point owns the session's lifetime** (`Depends(get_db)`, `task_session()`, or `async_session_factory()` in the CLI) and the **service owns the transaction**. Services take `db` and never open a session, so routes, tasks and the CLI call the same function. The architecture doc is rewritten accordingly (done with this plan).

An audit of `app/` against the rule found these places (the embedding task was added by GH-4 and found in a second pass):

| Where | Violation |
|-------|-----------|
| `app/tasks/user.py` | `_welcome_user` calls `db.get(User, user_id)` |
| `app/core/deps.py:33` | `get_current_user` calls `db.get(User, user_id)` |
| `app/routers/health.py:11` | `db.execute(text("SELECT 1"))` in a route |
| `app/cli/__main__.py` `_ping_db` | `engine.connect()` and `SELECT 1` in the CLI |
| `app/tasks/embedding.py` | `_mark_failed` calls `db.get(Document, ...)`, mutates the row and `db.commit()`s |
| `app/services/ingest.py` `crawl_and_store` | A service that opens its own session (the pattern the new rule drops) |

Clean, no change: `app/routers/auth.py`, `app/routers/user.py`, `app/routers/ingest.py`, `app/tasks/google_chat.py`, the middleware.

## Decisions

1. **Entry points own the session; services own the transaction.** Routes, tasks and the CLI contain no queries, `db.add`, `db.commit` or `db.execute`; they pass a session to a service.
2. **Services never open a session, and there are no `_for_task` twins.** One function per operation, taking `db`. `user_service.get(db, user_id)` serves `get_current_user` and the welcome task. The earlier `get_for_task` is removed.
3. **Tasks open a session with `task_session()` in a small async helper** driven by `asyncio.run`, because a Celery task has no request scope. The helper holds no logic beyond opening the session and calling the service. Retry logic (`RETRY_DELAYS`, `self.retry`) stays in the task.
4. **`get_db` stays in `app/core/deps.py`.** It is session provisioning for `Depends`.
5. **The CLI keeps opening its own sessions** (`async_session_factory()`) and disposing the engine. `_ping_db` now does the same instead of using a standalone connection, so `ping_db_standalone` is not needed.
6. **`crawl_and_store` is split.** The task helper crawls first, then opens the session only to store, so no database connection is held during the network call. This keeps the behaviour of the old `crawl_and_store`.
7. **Out of scope:** any change to `get_db` or `app/main.py` lifespan disposal.

## Code

`app/services/user.py`: `get(db, user_id)` only (already in place); `get_for_task` is removed.

`app/core/deps.py` (already in place):

```python
user = await user_service.get(db, user_id) if user_id is not None else None
```

`app/tasks/user.py`:

```python
async def _get_user(user_id: int) -> User | None:
    from app.services import user as user_service  # local: services.user imports this module

    async with task_session() as db:
        return await user_service.get(db, user_id)


@celery_app.task
def welcome_user(user_id: int) -> None:
    # SYNC-EXCEPTION: Celery task bodies are sync; asyncio.run drives the async work
    user = asyncio.run(_get_user(user_id))
    if user is None:  # deleted before the job ran; nothing to do
        logger.warning(f"welcome_user: user {user_id} not found")
        return
    logger.info(f"welcome {user.email}")  # stub: send the welcome mail here
```

`app/services/health.py` (new):

```python
async def ping_db(db: AsyncSession) -> None:
    await db.execute(text("SELECT 1"))
```

`app/routers/health.py`: `await health_service.ping_db(db)` in place of the `db.execute(...)` call.

`app/cli/__main__.py`: `_ping_db` opens `async_session_factory()`, calls `await health_service.ping_db(db)`, then `await engine.dispose()`.

`app/services/embedding/__init__.py` (addition):

```python
async def mark_failed(db: AsyncSession, document_id: int, error: str) -> None:
    document = await db.get(Document, document_id)
    if document is not None:
        document.status = DocumentStatus.FAILED
        document.error = error
        await db.commit()
```

`app/tasks/embedding.py`:

```python
async def _run(document_id: int) -> None:
    # one client per run: Celery tasks have no lifespan to share one
    async with task_session() as db:
        await run_embedding(db, document_id, get_embedder())


async def _mark_failed(document_id: int, error: str) -> None:
    async with task_session() as db:
        await embedding_service.mark_failed(db, document_id, error)
```

`app/tasks/crawler.py`:

```python
async def _crawl_and_store(url: str, collection_id: int):
    outcome, doc = await crawler_service.crawl_page(url)
    if doc is None:
        return outcome, None, None
    async with task_session() as db:  # opened after the network call
        return outcome, doc, await ingest.store_extracted(db, collection_id, doc)
```

## Files to create/modify

| File | Slice | Purpose |
|------|-------|---------|
| `docs/architecture/index.md` | done | Rewritten rule: entry point owns the session, service owns the transaction |
| `app/services/user.py` | 1, 2 | `get`; remove `get_for_task` |
| `app/core/deps.py` | 1 | `get_current_user` calls `user_service.get` |
| `app/tasks/user.py` | 2 | Task opens a session and calls `user_service.get` |
| `app/services/health.py` (new) | 3 | `ping_db` |
| `app/routers/health.py` | 3 | Calls `ping_db`; no `sqlalchemy` import |
| `app/cli/__main__.py` | 3 | `_ping_db` opens a session and calls `ping_db`; no `text` import |
| `app/services/embedding/__init__.py` | 4 | `mark_failed(db, ...)` |
| `app/tasks/embedding.py` | 4 | `_mark_failed` calls the service; no `Document` imports |
| `app/services/ingest.py` | 5 | Remove `crawl_and_store` |
| `app/tasks/crawler.py` | 5 | `_crawl_and_store` helper |
| `tests/integration/test_jobs.py` | 2 | Welcome tests against the task, `app.tasks.user.task_session` patched |
| `tests/integration/test_user_service.py` | 1 | `user_service.get` (done) |
| `tests/integration/test_health_service.py` (new) | 3 | `health.ping_db` |
| `tests/unit/test_cli.py` | 3 | `test_check_db` patches `health.ping_db` |
| `tests/integration/test_embedding_service.py` (new, or the existing embedding service test file) | 4 | `mark_failed` |
| `tests/unit/test_crawler.py` | 5 | Patch the new seams instead of `ingest.crawl_and_store` |

## Testing plan

No network, no Redis. DB tests use the `db_session` SQLite fixture.

- `user_service.get`: returns the user for a known id, `None` for an unknown one.
- `get_current_user`: `tests/integration/test_current_user.py` passes unchanged.
- Welcome task: patch `app.tasks.user.task_session` to yield `db_session`. Call `welcome_user` as a plain function. An existing user logs `welcome ann@example.com`; a missing user logs a warning and does not raise. These tests are sync, because the task calls `asyncio.run` itself.
- `health.ping_db`: runs on `db_session` without raising.
- `check-db`: patch `health_service.ping_db` and the session factory, and assert the output is `database ok`.
- `embedding_service.mark_failed`: sets `FAILED` and the error on an existing document, does nothing for a missing id.
- Embedding and crawl tasks: the existing retry and failure tests still pass, with patch targets updated where the old seams moved.
- `/health` tests (`test_health.py`, `test_rate_limit.py`, `test_trace.py`) pass unchanged.

## Verification

- `make test` and `make format` are clean.
- `grep -rnE "db\.(add|commit|execute|get|scalar|delete)|select\(|text\(" app/routers app/tasks app/cli app/core/deps.py` returns nothing. `task_session` and `async_session_factory` are allowed in entry points under the new rule.
- `grep -rn "task_session\|async_session_factory" app/services` returns nothing.
- `uv run cli check-db` prints `database ok` against a running Postgres, and `GET /health` returns 200.
- Register a user through the API with the worker running: the worker logs `welcome <email>`.
