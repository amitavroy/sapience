# Scaffold FastAPI Project with uv (GH-1)

## To-do

Each slice ends in a working, reviewable state. Pause for review after each slice.

| # | Slice | Step | Done |
|---|-------|------|------|
| 1 | Health endpoint | Install uv; `uv init` with Python 3.12 (`.python-version`, `requires-python`) | [x] |
| 1 | Health endpoint | `pyproject.toml`: deps, ruff config, pytest config | [x] |
| 1 | Health endpoint | `app/__init__.py`, `app/main.py`, `app/core/__init__.py`, `app/core/config.py` | [x] |
| 1 | Health endpoint | `app/routers/__init__.py`, `app/routers/health.py` (`GET /health`) | [x] |
| 1 | Health endpoint | `tests/conftest.py` (async client), `tests/integration/test_health.py` | [x] |
| 1 | Health endpoint | `.gitignore`, `.env.example` | [x] |
| 2 | Database layer | `app/db/base.py`, `app/db/session.py` (async engine, `expire_on_commit=False`) | [x] |
| 2 | Database layer | `app/core/deps.py` (DB session dependency) | [x] |
| 2 | Database layer | `docker-compose.yml` (Postgres with pgvector, Redis) | [x] |
| 2 | Database layer | `/health` also checks the DB; Docker-free test DB in `conftest.py` | [x] |
| 3 | Migrations | `alembic.ini`, async `alembic/env.py`, `script.py.mako`, `versions/` | [x] |
| 3 | Migrations | `app/models/__init__.py` imports all models so Alembic sees them | [x] |
| 4 | Logging, limiter, middleware | `app/core/logger.py` (loguru) | [x] |
| 4 | Logging, limiter, middleware | `app/core/limiter.py` (limits.aio, Redis storage) | [x] |
| 4 | Logging, limiter, middleware | Lifespan, middleware and limiter wiring in `main.py`; `app/middleware/` | [x] |
| 4 | Logging, limiter, middleware | Mock Redis and disable the limiter in `conftest.py` | [x] |
| 5 | CLI | `app/cli/__init__.py`, `app/cli/__main__.py` (Typer, one example command) and script entry | [x] |
| 6 | Tooling and CI | `.pre-commit-config.yaml` | [x] |
| 6 | Tooling and CI | `.github/workflows/ci.yml` (ruff + pytest) | [x] |
| 7 | Docker and docs | `Dockerfile` (uv-based) | [x] |
| 7 | Docker and docs | `README.md`: usage plus rename-the-project checklist | [x] |

## Context

The repo holds only a README and `temp.md`. The goal is a runnable, tested, containerised FastAPI starter managed by `uv`, laid out as in `temp.md`. Python is set up through uv: the host only has the macOS system Python 3.9.6 (EOL) and no uv.

## Decisions

1. **Python 3.12, pinned via uv.** `.python-version` and `requires-python = ">=3.12"`. uv downloads the interpreter, so the host Python is not used. Rationale: 3.9 is EOL and blocks current dependency versions.
2. **Project name is `fastapi`.** Python package is `app/`. Because the distribution name `fastapi` collides with the FastAPI library on PyPI, set the project's `[project] name` to something that doesn't shadow it (e.g. `fastapi-app`) while the repo and directory stay `fastapi`. The README rename checklist covers forks.
3. **Tests need no infra.** Redis is mocked and the limiter is disabled in `conftest.py`. The test DB is Docker-free (SQLite via `aiosqlite`). The pgvector Postgres and Redis containers exist only for local development.
4. **Async everywhere.** SQLAlchemy async engine, async Alembic `env.py`, `expire_on_commit=False` on the sessionmaker.
5. **Vertical slices.** Slice 1 is a working `/health` endpoint with a passing test before any infra is added.
6. **Settings** come from `pydantic-settings` (`core/config.py`), with `.env.example` documenting every variable.

## Target structure

Per `temp.md`:

```
project-root/
├── .github/workflows/ci.yml
├── alembic/ (env.py, script.py.mako, versions/)
├── app/
│   ├── main.py
│   ├── core/ (config.py, logger.py, limiter.py, deps.py)
│   ├── db/ (base.py, session.py)
│   ├── models/  schemas/  services/  middleware/
│   ├── routers/ (health.py)
│   └── cli/ (__main__.py)
├── tests/ (conftest.py, unit/, integration/test_health.py)
├── .env.example  .gitignore  .pre-commit-config.yaml
├── alembic.ini  docker-compose.yml  Dockerfile
├── pyproject.toml  uv.lock  README.md
```

## Dependencies (indicative)

- Runtime: `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic-settings`, `redis`, `slowapi`, `loguru`, `typer`.
- Dev: `pytest`, `pytest-asyncio`, `httpx`, `aiosqlite`, `fakeredis`, `ruff`, `pre-commit`.

## Files to create/modify

| File | Slice | Purpose |
|------|-------|---------|
| `pyproject.toml`, `.python-version`, `uv.lock` | 1 | Project, deps, ruff and pytest config |
| `app/main.py`, `app/core/config.py` | 1 | App factory and settings |
| `app/routers/health.py` | 1 | `GET /health` |
| `tests/conftest.py`, `tests/integration/test_health.py` | 1 | Async client and health test |
| `.gitignore`, `.env.example` | 1 | Repo hygiene and config docs |
| `app/db/*`, `app/core/deps.py`, `docker-compose.yml` | 2 | Async DB and dev infra |
| `alembic.ini`, `alembic/*`, `app/models/__init__.py` | 3 | Migrations |
| `app/core/logger.py`, `app/core/limiter.py`, `app/middleware/` | 4 | Logging, rate limiting |
| `app/cli/*` | 5 | Typer CLI |
| `.pre-commit-config.yaml`, `.github/workflows/ci.yml` | 6 | Lint and CI |
| `Dockerfile`, `README.md` | 7 | Container and docs |

## Testing plan

- Integration: `/health` returns 200 (slice 1), then also reports DB status (slice 2).
- Rate limiting: a test with the limiter enabled and Redis mocked proves requests over the limit get 429 (slice 4).
- CLI: a Typer `CliRunner` test for the example command (slice 5).
- All tests run with no Postgres or Redis available.

## Verification

- `uv sync && uv run pytest` passes with Docker stopped.
- `uv run ruff check .` and `uv run ruff format --check .` are clean.
- `docker compose up -d` starts Postgres (pgvector) and Redis; `uv run alembic upgrade head` succeeds against it.
- `uv run uvicorn app.main:app` serves `/health`.
- `docker build .` succeeds.
- CI workflow is green on a pushed branch.
