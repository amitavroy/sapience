# Request pipeline

Every request is rate limited per client IP, handled, then logged with its status and duration.

    request → rate_limit dependency → router → response → log_requests middleware
                   │
                   └─ over limit → 429 "Too many requests"

| Outcome | Status | Notes |
|---------|--------|-------|
| Within limit | route's own | Counted in Redis, fixed window |
| Over limit | 429 | `rate_limit` setting, default `60/minute` |

- The limiter is an app-wide dependency (`Depends(rate_limit)` in `main.py`). It uses `limits.aio` with Redis storage because slowapi's storage is sync and would block the event loop.
- The client key is `request.client.host`, or `"unknown"` if absent.
- Log line message: `GET /health 200 3.2ms` (every line also carries the request's trace id, see Logging and trace id).

# Logging and trace id

Every request gets a trace id that is on every log line it produces and is returned to the client.

    request → resolve trace id → logs carry trace_id → response header X-Request-ID
                  │
                  ├─ peer in TRUSTED_PROXIES and X-Request-ID matches [A-Za-z0-9-]{8,64} → use it
                  └─ otherwise → generate uuid4().hex

| Case | Trace id used | Notes |
|------|---------------|-------|
| No header | generated | |
| Header from untrusted peer | generated | Header value logged once as `client_request_id` (first 64 chars) |
| Header from trusted peer, valid | the header | |
| Header from trusted peer, malformed | generated | |

- `TRUSTED_PROXIES` is a comma-separated string of IPs or CIDRs in `.env` (e.g. `10.0.0.1, 192.168.0.0/16`). Empty (default) trusts nobody. The peer is the real socket address, `request.client.host`.
- If uvicorn runs with `--proxy-headers`, keep `--forwarded-allow-ips` equal to `TRUSTED_PROXIES`, and have the edge proxy overwrite any client-supplied `X-Request-ID`.
- Format: human-readable with the trace id when `DEBUG` is true; one JSON object per line otherwise (the id is under `record.extra.trace_id`). Lines outside a request show `-`.
- Each `uv run cli ...` invocation gets its own trace id.
- Jobs: none exist yet. When added, pass `trace_id` to the job and wrap it in `logger.contextualize(trace_id=..., job=name)` so job logs join the request's trace.

# Health check

`GET /health` runs `SELECT 1` through the request's DB session.

    request → DB session → SELECT 1 → {"status": "ok", "database": "ok"}
                               └─ DB unreachable → error response (not a 200)

The CLI equivalent is `uv run cli check-db`, which prints `database ok`.

# Authentication

Register, log in with JSON, then call protected routes with a bearer token.

    POST /auth/register → user          (409 if email taken, 422 if invalid)
    POST /auth/login    → access_token  (401 for wrong password, unknown email or inactive user)
    GET  /user          → current user  (needs Authorization: Bearer <token>)

- Passwords are hashed with argon2 (`pwdlib`) in a worker thread. `password_hash` is never returned.
- Tokens are HS256 JWTs: `sub` is the user id, `exp` is `ACCESS_TOKEN_EXPIRE_MINUTES` (default 30). There are no refresh tokens.
- Emails are stored lowercased. Login errors are identical, so they don't reveal which emails exist.
- `CurrentUser` (`app/core/deps.py`) returns 401 for a missing, invalid or expired token, or an inactive or deleted user.
- `uv run cli seed-user` creates a dev user from `SEED_USER_*`. It is idempotent and refuses when `DEBUG` is false unless `--force`.

# RAG data model

Users share collections; a collection holds documents; documents are split into embedded chunks that vector search runs over.

    users ──< collection_members >── collections ──< documents ──< chunks
                                          └──────────────────────────< chunks.collection_id

| Table | Key columns | Notes |
|-------|-------------|-------|
| `collections` | `name`, `description`, `created_by_id` | `created_by_id` is audit only; access comes from membership |
| `collection_members` | PK (`collection_id`, `user_id`), `role` | One role per user per collection: `owner`, `editor` or `viewer` (default) |
| `documents` | `collection_id`, `title`, `source_uri`, `content_hash`, `status`, `error`, `metadata` | `content_hash` (sha256) unique per collection; `status` is `pending` → `processing` → `ready` / `failed` |
| `chunks` | `document_id`, `collection_id`, `chunk_index`, `content`, `token_count`, `embedding`, `metadata` | `(document_id, chunk_index)` unique; `embedding` is `vector(1536)`, NULL until embedded |

When a row is deleted:

| Deleted | Effect |
|---------|--------|
| Collection | Its memberships, documents and chunks are deleted |
| Document | Its chunks are deleted |
| User | Their memberships are deleted; `collections.created_by_id` and `documents.uploaded_by_id` become NULL |

- Cascades run in the database (`ON DELETE CASCADE` / `SET NULL`); ORM relationships use `passive_deletes=True`.
- Embeddings are OpenAI `text-embedding-3-small` (1536 dims, `EMBEDDING_DIM` in `app/db/types.py`). Search uses the HNSW index `ix_chunks_embedding_hnsw` with cosine distance: `ORDER BY embedding <=> :query`. The ORM returns embeddings as a list of floats.
- `chunks.collection_id` duplicates the document's collection so search can filter by collection without a join.
- `metadata` is JSONB; the Python attribute is `meta` because `metadata` is reserved on SQLAlchemy models.
- The first migration of this feature runs `CREATE EXTENSION IF NOT EXISTS vector`, so any Postgres works as long as pgvector is installed on the server and the migration role may create extensions. Its downgrade leaves the extension in place.
- Changing the embedding size needs a new migration and re-embedding every chunk. HNSW on `vector` is limited to 2000 dims.

# Google Chat webhook

Google Chat @mentions and slash commands arrive at `POST /ingest/google-chat`. The endpoint verifies Google's ID token (401 on failure), replies "Got it" straight away, and queues the event for a Celery worker, which handles mentions and slash commands separately. Setup, env vars, event kinds and local testing: [google-bot.md](google-bot.md).
