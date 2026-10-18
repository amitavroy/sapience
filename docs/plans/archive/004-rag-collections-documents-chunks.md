# Add collections, documents and chunks tables for RAG (GH-1)

## To-do

Each slice ends in a working, reviewable state: tables exist, the migration runs on Postgres, and tests pass. Pause for review after each slice.

| # | Slice | Step | Done |
|---|-------|------|------|
| 1 | Collections | Add dep `pgvector`; `EMBEDDING_DIM = 1536` constant in `app/db/types.py` | [x] |
| 1 | Collections | Hand-written migration `enable vector extension`: `CREATE EXTENSION IF NOT EXISTS vector` (downgrade is a no-op) | [x] |
| 1 | Collections | `app/models/collection.py` (`Collection`, `CollectionMember`, `CollectionRole`) + register in `app/models/__init__.py` | [x] |
| 1 | Collections | Migration `create collections`; `alembic upgrade head` / `downgrade -1` round-trips on Postgres | [x] |
| 1 | Collections | `conftest.py`: enable SQLite `PRAGMA foreign_keys=ON`; tests: collection + owner membership, add second member, duplicate membership rejected, bad role rejected, deleting a user removes memberships | [x] |
| 2 | Documents | `app/models/document.py` (`Document`, `DocumentStatus`) + register | [x] |
| 2 | Documents | Migration `create documents` | [x] |
| 2 | Documents | Tests: create document, `meta` defaults to `{}`, duplicate `(collection_id, content_hash)` rejected, bad status rejected, deleting a collection deletes its documents | [x] |
| 3 | Chunks | `app/models/chunk.py` (`Chunk`) with `Vector(EMBEDDING_DIM)` + HNSW index + register | [x] |
| 3 | Chunks | Migration `create chunks`: import `pgvector.sqlalchemy`, HNSW index | [x] |
| 3 | Chunks | Tests: create chunks with embeddings, duplicate `(document_id, chunk_index)` rejected, deleting a document / collection deletes chunks | [x] |
| 3 | Chunks | Manual Postgres check: `\d chunks`, cosine query `ORDER BY embedding <=> :q` filtered by `collection_id` | [x] |
| 4 | Docs | Wiki section "RAG data model" (ER sketch, cascade rules); architecture "Known risks": vector search not covered by SQLite tests | [x] |

## Context

The app has users and auth (GH-2) but nothing to store RAG data in. This adds the storage layer: **collections** (shared groups of knowledge), **documents** (sources inside a collection) and **chunks** (embedded pieces of a document that vector search runs over). Postgres 17 with pgvector is already in `docker-compose.yml` (`pgvector/pgvector:pg17`), but the extension isn't enabled and no vector column exists yet.

This ticket covers the schema only (models, migrations, tests). Ingestion (upload, parsing, chunking, embedding via Celery), the collection/document APIs and search come in later tickets that build on these tables.

```
users ──< collection_members >── collections ──< documents ──< chunks
                                      └──────────────────────────< (chunks.collection_id)
```

## Decisions

1. **Access through membership.** A user can belong to many collections and a collection can have many users, via `collection_members` (composite PK `collection_id, user_id`) with a `role` of `owner`, `editor` or `viewer`. The creator is inserted as `owner`. `collections.created_by_id` is kept for audit only, not for access checks. Sharing a collection means inserting one row.
2. **Enums are strings plus CHECK constraints**, not native Postgres enums. Values are defined as Python `StrEnum` (`CollectionRole`, `DocumentStatus`). Adding a value later only needs a constraint change, not `ALTER TYPE`, and the constraint behaves the same on SQLite.
3. **Integer PKs**, as for `users`. `chunks.id` is `BigInteger` because chunk counts grow fastest.
4. **Embeddings:** OpenAI `text-embedding-3-small`, `vector(1536)`, held in one constant `EMBEDDING_DIM` in `app/db/types.py`. pgvector's HNSW index is limited to 2000 dimensions on `vector`, so `text-embedding-3-large` (3072) would need `halfvec` or a reduced `dimensions=` setting. That is a later decision, not part of this ticket. `embedding` is nullable so chunks can be stored before the embed step runs.
5. **Vector index:** HNSW with `vector_cosine_ops` (`m=16, ef_construction=64`). OpenAI embeddings are normalized, so cosine is the right distance. HNSW also needs no training data, unlike IVFFlat.
6. **Denormalized `chunks.collection_id`.** Search is always scoped to a collection. Storing `collection_id` on each chunk avoids a join to `documents` in the hot query and allows a B-tree filter next to the vector index.
7. **One shared `chunks` table**, not a table per collection. This is the standard pgvector layout. Partial indexes or partitioning can be added later if one collection becomes very large.
8. **Cascades at the DB level.** `ON DELETE CASCADE` runs from collection to documents and chunks, and from collection or user to memberships. `created_by_id` and `uploaded_by_id` use `ON DELETE SET NULL`. ORM relationships use `passive_deletes=True` so SQLAlchemy leaves the deleting to the DB instead of loading children.
9. **Dedup:** `documents.content_hash` is the sha256 of the raw content, with `UNIQUE(collection_id, content_hash)`. The same file can exist in two collections but not twice in one. `UNIQUE(document_id, chunk_index)` keeps chunk order stable.
10. **Ingest state on the document:** a `status` (`pending` → `processing` → `ready` / `failed`) plus an `error` text column. The future Celery pipeline updates it, and a status endpoint can read it.
11. **Free-form metadata:** a `meta` attribute mapped to a `metadata` column, `JSON().with_variant(JSONB(), "postgresql")`, `server_default='{}'`. The attribute can't be named `metadata` because SQLAlchemy reserves that name on `Base`.
12. **SQLite tests:** the `embedding` column type is `Vector(EMBEDDING_DIM).with_variant(JSON(), "sqlite")`, so `create_all` works in tests. SQLite doesn't enforce FKs by default, so the test engine turns on `PRAGMA foreign_keys=ON` (a `connect` event listener in `conftest.py`) for cascade tests to mean anything. Vector distance queries can't run on SQLite and are checked by hand on Postgres (see Verification).
13. **One migration per slice**, autogenerated, then edited by hand. Autogenerate doesn't emit the `pgvector` import, so it is added to the chunks migration manually.
14. **The extension is enabled by a migration, not by Docker.** Postgres may run outside `docker-compose`, for example on another server or a managed service, so nothing can rely on the `pgvector/pgvector` image or an init script. The first migration of this ticket is a separate, hand-written `enable vector extension` revision that runs `CREATE EXTENSION IF NOT EXISTS vector`. Every later migration depends on it. `IF NOT EXISTS` makes it safe on servers where a DBA already enabled the extension.
    - **Server requirements:** the pgvector binaries must be installed on that Postgres server (e.g. the `postgresql-17-pgvector` package, or allow-listed on managed services). The migration role also needs the right to create the extension: superuser, database owner if the extension is trusted, or `rds_superuser` / `azure_pg_admin` on managed services. If either is missing, `alembic upgrade` fails at this first step with a clear error, before any tables are created.
    - **Downgrade is a no-op:** it does not drop the extension, which other databases or schemas on a shared server may use.

## Code sketches

`app/models/collection.py`

```python
class CollectionRole(StrEnum):
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    members: Mapped[list["CollectionMember"]] = relationship(
        back_populates="collection", cascade="all, delete-orphan", passive_deletes=True
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="collection", cascade="all, delete-orphan", passive_deletes=True
    )


class CollectionMember(Base):
    __tablename__ = "collection_members"
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'editor', 'viewer')", name="ck_collection_members_role"),
    )

    collection_id: Mapped[int] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    role: Mapped[str] = mapped_column(String(20), default=CollectionRole.VIEWER)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

`app/models/document.py` (key columns)

```python
class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("collection_id", "content_hash", name="uq_documents_collection_hash"),
        CheckConstraint(
            "status IN ('pending', 'processing', 'ready', 'failed')", name="ck_documents_status"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    collection_id: Mapped[int] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), index=True
    )
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(500))
    source_uri: Mapped[str | None] = mapped_column(String(1000))
    mime_type: Mapped[str | None] = mapped_column(String(100))
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(
        String(20), default=DocumentStatus.PENDING, server_default="pending"
    )
    error: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column("metadata", JSONType, default=dict, server_default="{}")
    # created_at / updated_at as in User
```

`app/models/chunk.py` (key columns)

```python
from app.db.types import EMBEDDING_DIM

EmbeddingType = Vector(EMBEDDING_DIM).with_variant(JSON(), "sqlite")


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunks_document_index"),
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), primary_key=True
    )
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    collection_id: Mapped[int] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int]
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int]
    embedding: Mapped[list[float] | None] = mapped_column(EmbeddingType)
    meta: Mapped[dict] = mapped_column("metadata", JSONType, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

`JSONType = JSON().with_variant(JSONB(), "postgresql")` lives in `app/db/types.py` and is shared by documents and chunks. The `BigInteger` → `Integer` variant on SQLite keeps autoincrement working there.

Extension migration (hand-written, `alembic revision -m "enable vector extension"`, first in this ticket):

```python
def upgrade() -> None:
    # Postgres may run outside Docker; the pgvector binaries must be installed on the server.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    # Leave the extension in place: other databases/schemas on the server may use it.
    pass
```

Chunks migration (manual addition):

```python
import pgvector.sqlalchemy  # noqa: F401  (autogenerate references it without importing)
```

## Files to create/modify

| File | Slice | Purpose |
|------|-------|---------|
| `pyproject.toml`, `uv.lock` | 1 | `pgvector` dependency |
| `app/db/types.py` | 1, 2 | `EMBEDDING_DIM` (slice 1); shared `JSONType` JSON / JSONB variant (slice 2) |
| `app/models/collection.py`, `app/models/__init__.py` | 1 | `Collection`, `CollectionMember`, `CollectionRole` |
| `alembic/versions/<rev>_enable_vector_extension.py` | 1 | `CREATE EXTENSION IF NOT EXISTS vector` |
| `alembic/versions/<rev>_create_collections.py` | 1 | Collections + members migration |
| `tests/conftest.py` | 1 | `PRAGMA foreign_keys=ON` for SQLite |
| `tests/integration/test_collection_models.py` | 1 | Membership and cascade tests |
| `app/models/document.py`, `app/models/__init__.py` | 2 | `Document`, `DocumentStatus` |
| `alembic/versions/<rev>_create_documents.py` | 2 | Documents migration |
| `tests/integration/test_document_models.py` | 2 | Dedup, status and cascade tests |
| `app/models/chunk.py`, `app/models/__init__.py` | 3 | `Chunk` |
| `alembic/versions/<rev>_create_chunks.py` | 3 | Chunks table, HNSW index |
| `tests/integration/test_chunk_models.py` | 3 | Ordering uniqueness and cascade tests |
| `docs/wiki/index.md`, `docs/architecture/index.md` | 4 | Data model docs, known-risk note |

## Testing plan

- Integration tests on the SQLite test DB through the existing `db_session` fixture, with FKs enforced:
  - **Collections:** create a collection and its owner membership; add a second user as a viewer; a duplicate `(collection_id, user_id)` raises `IntegrityError`; an invalid role raises `IntegrityError`; deleting a user removes their memberships and sets `created_by_id` to NULL.
  - **Documents:** create a document and check that `status` defaults to `pending` and `meta` to `{}`; a duplicate hash in the same collection is rejected, but the same hash in another collection is allowed; an invalid status is rejected; deleting a collection deletes its documents.
  - **Chunks:** store chunks with 1536-float embeddings and read them back; a duplicate `(document_id, chunk_index)` is rejected; deleting a document or a collection deletes its chunks.
- No vector-distance tests on SQLite (Decision 12). The distance query is checked by hand on Postgres.

## Verification

- `uv run pytest` passes with no Postgres or Redis.
- `uv run ruff check .` and `uv run ruff format --check .` are clean.
- `docker compose up -d db && uv run alembic upgrade head` creates all four tables. `uv run alembic downgrade base && uv run alembic upgrade head` round-trips cleanly.
- In `psql`, `\d chunks` shows `embedding vector(1536)` and `ix_chunks_embedding_hnsw ... USING hnsw (embedding vector_cosine_ops)`, and `\dx` lists `vector`.
- Manual query: insert a collection, a document and a few chunks with random 1536-dim vectors, then run `SELECT id FROM chunks WHERE collection_id = :c ORDER BY embedding <=> :q LIMIT 5`. It returns rows, and `EXPLAIN` shows the HNSW index once there are enough rows (or with `SET enable_seqscan = off`).
- Non-Docker Postgres: on a fresh database where pgvector is installed but the extension isn't enabled, `alembic upgrade head` creates it (`\dx` lists `vector`). Running it again is a no-op. On a server without the pgvector binaries, the upgrade fails at the extension revision with "could not open extension control file", and no tables are created.
- Known risk: SQLite tests can't cover pgvector types or JSONB behaviour. Search behaviour gets proper coverage in the retrieval ticket, ideally with a Postgres-backed test job.
