# Add User model, registration, login and GET /user (GH-2)

## To-do

Each slice ends in a working, reviewable state. Pause for review after each slice.

| # | Slice | Step | Done |
|---|-------|------|------|
| 1 | Register | Add deps `pwdlib[argon2]`, `PyJWT`; `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES` in `config.py` and `.env.example` | [x] |
| 1 | Register | `app/models/user.py` (+ import in `app/models/__init__.py`); autogenerate and commit first Alembic migration | [x] |
| 1 | Register | `app/core/security.py` (hash/verify off-loop, flagged SYNC-EXCEPTION; update architecture table) | [x] |
| 1 | Register | `app/schemas/user.py` (`UserCreate`, `UserRead`), `app/services/user.py`, `app/routers/auth.py` `POST /auth/register`; wire in `main.py` | [x] |
| 1 | Register | `conftest.py` creates tables; tests: register ok, duplicate email 409, bad email/short password 422, hash not exposed | [x] |
| 2 | Login | JWT create/decode in `security.py`; `app/schemas/auth.py` (`Token`); `POST /auth/login` | [x] |
| 2 | Login | Tests: valid login returns token, wrong password / unknown email / inactive all 401 | [x] |
| 3 | Current user | `CurrentUser` dependency in `deps.py`; `app/routers/user.py` `GET /user` | [x] |
| 3 | Current user | Tests: valid token returns user, no token / garbage / expired token / inactive user 401 | [x] |
| 4 | Seeder | `seed-user` command in `app/cli/__main__.py` (reuses the user service); idempotent; refuses when `DEBUG` is false unless `--force`; CliRunner tests | [x] |
| 5 | Docs | README: auth usage with curl; wiki section "Authentication"; run `uv run alembic upgrade head` against Postgres | [x] |

## Context

The scaffold (GH-1) has plumbing but no real feature: `app/models`, `app/schemas` and `app/services` are empty and no migration exists. This adds the first reference slice: a `User` model, registration, login returning a token, and a protected `GET /user` returning the current user. It becomes the pattern to copy for later features.

## Decisions

1. **User fields:** `id`, `name`, `email` (unique, indexed, stored lowercased), `password_hash`, `is_active` (default true), `created_at`, `updated_at` (server defaults, `updated_at` onupdate).
2. **Tokens:** JWT access token via `PyJWT`, HS256, `sub` = user id, `exp` from `ACCESS_TOKEN_EXPIRE_MINUTES` (default 30). New settings: `SECRET_KEY` (required), `ACCESS_TOKEN_EXPIRE_MINUTES`. No refresh tokens yet.
3. **Password hashing:** `pwdlib[argon2]`. Hashing is CPU-bound, so per `docs/architecture/index.md` it runs via `asyncio.to_thread`, flagged `# SYNC-EXCEPTION` and added to the Sync exceptions table.
4. **Login shape:** `POST /auth/login` takes JSON (`email`, `password`); returns `{access_token, token_type: "bearer"}`. Wrong password, unknown email and inactive user all return the same 401 (no user enumeration).
5. **Routes:** `POST /auth/register` (201, returns user, 409 on duplicate email), `POST /auth/login`, `GET /user` (needs `Authorization: Bearer`; returns current user, 401 if missing/invalid/expired or user inactive/deleted).
6. **Layers:** router → service (`app/services/user.py`) → model. Schemas never expose `password_hash`.
7. **Security:** `app/core/security.py` holds hash/verify/create_token/decode_token. `app/core/deps.py` gets a `CurrentUser` dependency next to `DbSession`.
8. **Test DB:** the existing `db_session` fixture creates no tables; add `Base.metadata.create_all` to it in `conftest.py`.
9. **Rate limiting:** the global limiter already covers the new routes; no per-route limits now.
10. **Seeder:** Typer command `uv run cli seed-user` (no new package; Faker/polyfactory can be layered on later for bulk fake data). Options `--name`, `--email`, `--password` default to `SEED_USER_NAME`, `SEED_USER_EMAIL`, `SEED_USER_PASSWORD` (settings and `.env.example`, dev-only values). It calls the same user service as registration so hashing is identical, and uses the `asyncio.run(...)` pattern of `check_db`.
11. **Seeder safety:** idempotent (existing email prints "user exists", exits 0). If `settings.debug` is false it exits non-zero with an error unless `--force` is passed, so a default password can't land in production by accident.

## Files to create/modify

| File | Slice | Purpose |
|------|-------|---------|
| `app/models/user.py`, `app/models/__init__.py` | 1 | `User` model, registered for Alembic |
| `alembic/versions/<rev>_create_users.py` | 1 | First migration |
| `app/core/security.py` | 1, 2 | Hash/verify, JWT create/decode |
| `app/schemas/user.py`, `app/services/user.py`, `app/routers/auth.py` | 1 | Registration |
| `app/core/config.py`, `.env.example`, `pyproject.toml`, `uv.lock` | 1 | Settings and deps |
| `tests/conftest.py`, `tests/integration/test_register.py` | 1 | Tables in test DB, register tests |
| `app/schemas/auth.py`, `tests/integration/test_login.py` | 2 | Token schema, login tests |
| `app/core/deps.py`, `app/routers/user.py`, `tests/integration/test_current_user.py` | 3 | `CurrentUser`, `GET /user` |
| `app/cli/__main__.py`, `app/core/config.py`, `.env.example`, `tests/unit/test_cli.py` | 4 | `seed-user` command, seed settings, tests |
| `app/main.py` | 1, 3 | Include routers |
| `docs/architecture/index.md`, `README.md`, `docs/wiki/index.md` | 1, 5 | Sync exception row, usage docs |

## Testing plan

- Integration (SQLite test DB, no Redis): register (ok, duplicate 409, invalid input 422, no `password_hash` in response), login (ok, wrong password, unknown email, inactive user), `GET /user` (valid token, missing, garbage, expired, inactive user).
- CLI (`CliRunner`, in-memory SQLite): `seed-user` creates the user, a second run reports "user exists" and creates no duplicate, the seeded user can log in, and with `DEBUG=false` it fails unless `--force` is passed.
- Expired token is built with `create_token` and a negative expiry, not by sleeping.

## Verification

- `uv run pytest` passes with no Postgres or Redis.
- `uv run ruff check .` and `uv run ruff format --check .` are clean.
- `docker compose up -d && uv run alembic upgrade head` creates `users`.
- Manual: register, login (copy the token), then `curl -H "Authorization: Bearer <token>" localhost:8000/user` returns the user; the same call without a token returns 401.
- `DEBUG=true uv run cli seed-user` creates the default user; a second run prints "user exists"; the user can log in. With `DEBUG=false` it fails without `--force` and works with it.
- Known risk: SQLite tests don't prove Postgres unique-constraint behaviour; the 409 path relies on a pre-check plus catching `IntegrityError`.
