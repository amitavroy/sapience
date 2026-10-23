# Sapience

Async FastAPI starter managed with [uv](https://docs.astral.sh/uv/): SQLAlchemy (async) + Alembic, Redis rate limiting, loguru, Typer CLI. Architecture rules: [docs/architecture/index.md](docs/architecture/index.md).

## Usage

```sh
uv sync                              # install deps (Python 3.12 is fetched by uv)
uv run pre-commit install            # git hook: ruff + pytest on every commit
cp .env.example .env                 # then adjust values
docker compose up -d                 # Postgres (pgvector) + Redis for local dev
make migrate                         # apply migrations + create checkpoint tables
uv run uvicorn app.main:app --reload # serve; try GET /health
```

Tests need no Postgres or Redis:

```sh
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Migrations: add a model, import it in `app/models/__init__.py`, then
`uv run alembic revision --autogenerate -m "message"`.

Docker image: `docker build -t fastapi . && docker run --env-file .env -p 8000:8000 fastapi`
(`DATABASE_URL` and `REDIS_URL` must be reachable from the container).

The pre-commit hook runs `ruff check --fix`, `ruff format` (Python files and Python code blocks in Markdown) and `pytest`. CI runs the same ruff checks, so a clone without the hook can pass locally and fail CI. Check everything once with `uv run pre-commit run --all-files`.

## Auth

```sh
curl -X POST localhost:8000/auth/register -H 'Content-Type: application/json' \
  -d '{"name":"Ann","email":"ann@example.com","password":"supersecret"}'

curl -X POST localhost:8000/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"ann@example.com","password":"supersecret"}'
# → {"access_token":"<token>","token_type":"bearer"}

curl -H "Authorization: Bearer <token>" localhost:8000/user   # the user; 401 without a token
```

Set `SECRET_KEY` in `.env` (`openssl rand -hex 32`). In Swagger (`/docs`), paste the token into Authorize.
For a dev user: `uv run cli seed-user` (needs `DEBUG=true`, or pass `--force`). Details: [docs/wiki/index.md](docs/wiki/index.md).

## CLI

Management commands live in `app/cli/__main__.py` (Typer). Run them from the repo root:

```sh
uv run cli --help          # list commands
uv run cli check-db        # check the database is reachable → "database ok"
uv run cli seed-user       # create the dev user from SEED_USER_* (idempotent)
```

`python -m app.cli check-db` works too. The database URL comes from `.env` (`DATABASE_URL`).

No Docker? Use a throwaway in-memory SQLite database:

```sh
DATABASE_URL=sqlite+aiosqlite:///:memory: uv run cli check-db
```

To add a command, decorate a function with `@app.command()` in `app/cli/__main__.py`. For async work, call it through `asyncio.run(...)` as `check_db` does.

## Using this as a template (rename checklist)

- [ ] `pyproject.toml`: change `name` (keep it different from `fastapi`, which is the library's PyPI name)
- [ ] `app_name` default in `app/core/config.py` and `APP_NAME` in `.env.example`
- [ ] Database name: `POSTGRES_DB` and the end of `DATABASE_URL` in `.env.example` (and your `.env`)
- [ ] This README: title and description
- [ ] Docker image tag in the `docker build` command above
- [ ] `uv sync` again to refresh `uv.lock`
