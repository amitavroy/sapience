# Sapience

Async FastAPI service (Python 3.12, managed with uv): SQLAlchemy async + Alembic on Postgres/pgvector, Redis (rate limit, queues), Celery workers, Typer CLI. It ingests web pages into RAG collections and runs FocalBot, a Google Chat app. Setup and usage: `README.md`.

## Commands

```sh
make dev       # dev server with reload
make worker    # Celery worker (--pool=solo)
make migrate   # alembic upgrade head
make test      # uv run pytest
make format    # ruff format + ruff check --fix
uv run cli --help
```

Before saying a task is done: `uv run ruff check . && uv run ruff format --check . && uv run pytest`. Tests need no Postgres or Redis: SQLite via aiosqlite, and Redis is never contacted (the rate limiter is overridden, Celery publishing is stubbed or refused in `tests/conftest.py`). A Stop hook (`.claude/hooks/check.sh`) runs the same checks; do not bypass it.

## Layout

- `app/routers/`, `app/tasks/`, `app/cli/`, `app/core/deps.py`: entry points. Thin.
- `app/services/`: all business logic and all persistence.
- `app/models/`, `app/schemas/`, `app/db/`, `app/core/` (config, security, clients), `app/agent/` (LangGraph conversation agent), `app/middleware/`.
- `alembic/` migrations; new models must be imported in `app/models/__init__.py`.
- `tests/unit`, `tests/integration`, `tests/fixtures`.
- `docs/architecture/index.md` (rules, read it), `docs/architecture/adr.md` (decisions), `docs/wiki/` (how each feature works), `docs/plans/` (active plans; finished ones go to `docs/plans/archive/`), `docs/bruno/` (API requests).

## Rules

The full rules are in `docs/architecture/index.md`. The ones that matter most:

- **Persistence lives in services.** No `db.add/commit/execute/get/delete` or queries in routes, tasks, deps or the CLI. A service takes an `AsyncSession` as its first argument and never opens one. The entry point owns the session's lifetime, the service owns the transaction.
- **Async first.** `async def` handlers, async DB, `httpx.AsyncClient`, async Redis (`coredis`). Never block the event loop. If something cannot be async, isolate it (`asyncio.to_thread`), mark the line `# SYNC-EXCEPTION: <why>`, and add a row to the table in the architecture doc. If a task would need a sync approach, stop and flag it first.
- **Don't hold a DB session during slow network work** (crawling, LLM calls); open it after.
- **Settings** live in `app/core/config.py` and `.env.example` together. Add both, with a comment. Secrets are never committed (`.env`, `secrets/`).
- **Logging** uses loguru with the request/job trace id; log Google/LLM status and messages, never tokens, keys or assertions.

## Conventions

- Ruff: line length 100, rules `E F I UP B ASYNC`. Match the surrounding code's naming and comment density; comments say why, not what.
- Tests are async (`asyncio_mode = "auto"`). No test calls a real LLM, Google or Redis; use the fixtures and stubs in `tests/conftest.py`. Test behavior, including the failure paths.
- Behavior that cannot be covered under SQLite (pgvector search) is flagged and verified by hand.
- When a feature changes behavior, update its page in `docs/wiki/` in the same work.

## Workflow

- Work is ticket-driven: GitHub issue `GH-<n>`, a plan in `docs/plans/NNN-name.md` titled `# Title (GH-n)` with a To-do table.
- Skills: `/do-create-ticket` (requirement to plan), `/do-work <plan>` (exactly one task, then stop and report), `/do-commit`, `/do-merge`, `/do-close-ticket` (checks the To-do table, updates the wiki index, closes the issue, archives the plan).
- Do one plan task at a time, in order. Flip its checkbox in the plan when done.
- Commits: conventional prefix (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`), imperative subject, ticket at the end (`(GH-7)`), short bullet body. **Never commit, push or merge without the user's explicit go-ahead for that action.** Show the draft message in the reply and wait.
- Review criteria are in `REVIEW.md`.
