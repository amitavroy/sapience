# Persist crawled pages, chunk them by structure, and embed the chunks (GH-4)

## To-do

Each slice ends in a working, reviewable state. Pause for review after each slice. Slice 1 makes a crawled page appear as a `documents` row. Slices 2 and 3 add chunks you can inspect with `cli show-chunks`. Slice 4 makes the document `ready` with embeddings.

| # | Slice | Step | Done |
|---|-------|------|------|
| 1 | Store the page | Migration: nullable `documents.content` (JSON / JSONB); model maps it with `deferred()`; fix the `content_hash` comment | [x] |
| 1 | Store the page | `app/cli/__main__.py`: `create-collection <name> [--description] [--owner-email]` prints the new id | [x] |
| 1 | Store the page | `crawl-url <url> --collection <id>` (required): the CLI checks the collection exists, and `collection_id` travels in the task args (including retry args) | [x] |
| 1 | Store the page | `app/services/ingest.py`: `store_extracted(db, collection_id, doc)` inserts a `pending` `Document` with `content`, or reports `DUPLICATE` / `COLLECTION_MISSING` | [x] |
| 1 | Store the page | `crawl_url` task: after extraction, call the ingest service and log `stored document <id>` / `duplicate of document <id>` / `collection <id> not found` | [x] |
| 1 | Store the page | Tests: create-collection, crawl-url validation and enqueue, ingest stores, duplicate, missing collection, task retry args carry `collection_id` | [x] |
| 2 | Chunk by section | `app/services/chunking/`: `Chunker` protocol, `ChunkDraft`, `chunker_for(mime_type)` registry, `estimate_tokens` (characters ÷ 4, no dependency) | [x] |
| 2 | Chunk by section | `WebChunker` v1: block rendering, section packing (merge small sections in the same branch, split large sections at block boundaries, fold a tiny tail back), `heading_path` + block range in meta | [x] |
| 2 | Chunk by section | Ingest: chunk in the same transaction as the document insert (through `asyncio.to_thread`); chunks stored with `embedding` NULL; log chunk count and total tokens | [x] |
| 2 | Chunk by section | `cli show-chunks <document-id>`: prints each chunk's index, tokens, heading path and content | [x] |
| 2 | Chunk by section | `SYNC-EXCEPTION` comment and a row in `docs/architecture/index.md` for chunking | [x] |
| 2 | Chunk by section | Tests: merging, splitting, no lost text, contiguous `chunk_index`, meta, registry, ingest stores chunks | [x] |
| 3 | Overlap and oversized blocks | Overlap tail (whole blocks or trailing sentences, up to `overlap_tokens`) between pieces of one split section; never across sections | [x] |
| 3 | Overlap and oversized blocks | Oversized-block splitting: paragraph/quote by sentences, list by items, table by rows with the header row repeated, code by lines, hard token cut as a last resort | [x] |
| 3 | Overlap and oversized blocks | Tests: overlap present inside a split section and absent across sections; every chunk ≤ `max_tokens`; table header repeated; code split on lines | [x] |
| 4 | Embed | Add `openai` (`uv add openai`; the SDK is used for OpenRouter too); settings `embedding_provider`, `embedding_base_url`, `embedding_api_key`, `embedding_model`, `embedding_batch_size`, `embedding_timeout_seconds` in `config.py` and `.env.example` | [x] |
| 4 | Embed | `app/services/embedding/`: `Embedder` protocol, `EmbedResult` (vectors, tokens, cost), `EmbeddingError(retryable)`, `OpenAICompatibleEmbedder` (OpenRouter by default), `get_embedder()`; `embedding_input(title, chunk)` | [ ] |
| 4 | Embed | `app/tasks/embedding.py`: `embed_document` task (status transitions, batches, commit per batch, retries 5 s / 15 s / 60 s, `failed` with `error`); register it in `celery_app.include` | [ ] |
| 4 | Embed | Crawl task enqueues `embed_document` after a store, and re-enqueues it for a `pending` duplicate | [ ] |
| 4 | Embed | Tests with a fake embedder: fills embeddings, `ready`, batching, resume, retryable vs permanent, already `ready` is a no-op | [ ] |
| 5 | Tune on real pages | Crawl 3–5 real sites, review `show-chunks` output together, adjust sizes and rules, bump `WebChunker.version` if the logic changes | [ ] |
| 6 | Docs | Wiki entry `docs/wiki/ingestion.md` (pipeline, statuses, chunking rules, settings, limits); update `docs/wiki/web-crawl.md` and `docs/wiki/index.md` | [ ] |

## Context

`crawl-url` (GH-3, plan 008) fetches one page and extracts it into an `ExtractedDocument`: typed `blocks`, `sections` as index ranges with a `heading_path`, `links`, and a `content_hash`. It only logs the result. The tables for storing it already exist (plan 004):

- `collections` / `collection_members`.
- `documents`: `status` (`pending`, `processing`, `ready`, `failed`), `error`, `content_hash`, unique `(collection_id, content_hash)`.
- `chunks`: `chunk_index`, `content`, `token_count`, `embedding vector(1536)` (nullable, "NULL until the embed step has run"), `metadata`, denormalised `collection_id`, an HNSW cosine index.

This ticket fills those tables: it stores the page, chunks it with a web-specific strategy, and embeds the chunks. Retrieval comes later.

The approach was discussed before this ticket: save first and embed afterwards, structure-aware chunking with overlap only inside split sections, and a chunking strategy chosen by MIME type so PDFs can get their own later.

Codebase facts that shape the design:

- Celery tasks are sync and drive async work with `asyncio.run`. Database access in a task goes through `task_session()` (`app/db/session.py`), a throwaway `NullPool` engine per run, because a pooled asyncpg engine is bound to one event loop.
- `task_acks_late=True`: tasks must be idempotent.
- The crawl task passes `url` and `trace_id` positionally in `self.retry(args=...)` (`app/tasks/crawler.py`). A new positional argument must go into those `args` too.
- The CLI is Typer with sync commands calling `asyncio.run`, and it disposes the engine afterwards (`_seed_user`).
- `docs/architecture/index.md`: outbound calls need an explicit timeout and retry policy; OpenAI and OpenRouter are called through `openai.AsyncOpenAI` (OpenRouter with `base_url`); CPU-bound work in async code needs a `SYNC-EXCEPTION` flag and a table row.
- Plan 008 decision 28 already chose where the extraction goes: one nullable JSON column on `documents`, mapped `deferred()`, with no staging table.
- Tests run on SQLite, where `chunks.embedding` is JSON. The fake embedder's vectors are stored as lists.

## Decisions

### Pipeline

1. **Save first, then embed: two stages, two tasks.**

   ```
   crawl_url ── extract ── store Document + chunks (one transaction, status=pending, embedding NULL)
             └─ enqueue embed_document(document_id)
   embed_document ── status=processing ── batches of chunks → embeddings (commit per batch) ── status=ready
   ```

   Compared with embedding each chunk as it is made:
   - A failed embedding call retries only the embed step. The page is never fetched or chunked again.
   - Chunks are embedded about 100 per API call instead of one per call.
   - Crawler politeness (per host) and the embedding provider's rate limits are separate concerns in separate tasks.
   - Changing the chunker or the embedding model later only needs the stored data, not a recrawl.

   The cost is a short window where a document exists but has no embeddings yet. Retrieval (a later ticket) filters on `documents.status = 'ready'`.
2. **Status meanings.**

   | Status | Meaning |
   |--------|---------|
   | `pending` | Stored and chunked, waiting for embeddings |
   | `processing` | `embed_document` is running (or died mid-run; see decision 22) |
   | `ready` | Every chunk has an embedding |
   | `failed` | Embedding failed permanently; `error` says why. Chunks stay, so it can be retried later |

   A crawl or chunking failure stores nothing (the transaction rolls back), so no document is ever `failed` because of the crawl.
3. **The crawl task stores; it does not embed.** After `crawl_page` returns a document, the same `asyncio.run` call runs `ingest.store_extracted` in a `task_session()`. The task then calls `embed_document.delay(document_id, trace_id)` from its sync body, after the transaction has committed.

### Collections and the CLI

4. **`cli create-collection <name> [--description TEXT] [--owner-email EMAIL]`.** It inserts a `Collection` and prints `collection created: <id> (<name>)`. With `--owner-email`, it looks the user up (exit code 1 if none), sets `created_by_id`, and adds a `CollectionMember` with role `owner`. Without it, the collection has no members, which is fine for trusted local CLI use. Access control matters once there is an API.
5. **`crawl-url <url> --collection <id>`, required.** Before enqueueing, the CLI checks that the collection exists (one async query, then the engine is disposed like `_seed_user`) and exits with code 1 with `collection <id> not found` otherwise. The task signature becomes `crawl_url(self, url, trace_id, collection_id, attempt=0, requeues=0)`, and both `self.retry` calls pass `args=(url, trace_id, collection_id)`.
6. **The task checks the collection again.** It could be deleted between enqueue and run. `store_extracted` returns `COLLECTION_MISSING` and the task logs a WARNING and returns, rather than hitting a foreign key error.
7. **`uploaded_by_id` stays NULL** for CLI crawls. The CLI has no logged-in user, and the collection's owner didn't necessarily ask for this crawl.

### Storing the document (`app/services/ingest.py`)

8. **The full extraction goes in `documents.content`.** It is a nullable `JSONType` column (JSONB on Postgres), mapped with `deferred()` so list queries don't load it, holding `doc.model_dump(mode="json", exclude_defaults=True)`: blocks, sections, links, metadata, fetch fields. Postgres TOAST compresses large values. Re-chunking and the future link-following both read from it. The `content_hash` comment changes from "raw content" to "normalised extracted text (`ExtractedDocument.content_hash`)".
9. **Column mapping.**

   | `Document` column | From `ExtractedDocument` |
   |-------------------|--------------------------|
   | `title` | `title`, truncated to 500 characters |
   | `source_uri` | `source_uri`, truncated to 1000 characters |
   | `mime_type` | `mime_type` |
   | `content_hash` | `content_hash` |
   | `meta` | `metadata` plus `requested_url`, `status_code`, `fetched_at`, and `chunker` / `chunker_version` (from slice 2) |
   | `content` | the full dump (decision 8) |
   | `status` | `pending` |

10. **Duplicates use the existing unique constraint.** Before inserting, look up `(collection_id, content_hash)`. If a document exists, return `DUPLICATE` with its id and store nothing. An `IntegrityError` on insert (two tasks racing on the same page) is caught and treated the same way.
    - **Recrawling a changed page is out of scope.** A changed page at the same URL has a new hash, so it becomes a *second* document, and both are searchable. This is a known limit until the recrawl ticket.
11. **Idempotency.** With `acks_late`, a crawl task can run twice. The second run finds a duplicate and stores nothing. To cover a worker dying after the commit but before `embed_document.delay`, a duplicate whose status is `pending` gets `embed_document` enqueued again (decision 21 makes that safe).
12. **One transaction per page.** The document row, its chunks and the `chunker` meta are committed together, or not at all.

    ```python
    class StoreOutcome(StrEnum):
        STORED = "stored"
        DUPLICATE = "duplicate"
        COLLECTION_MISSING = "collection_missing"


    @dataclass(frozen=True)
    class StoreResult:
        outcome: StoreOutcome
        document_id: int | None = None
        status: str | None = None  # of the existing document, for DUPLICATE
        chunks: int = 0
        tokens: int = 0
    ```

### Chunking (`app/services/chunking/`)

13. **A strategy per source type, chosen by MIME type.** This is the Python equivalent of a Laravel contract with bound implementations:

    ```python
    class Chunker(Protocol):
        name: str  # "web"
        version: int  # bump when the output for the same input changes

        def chunk(self, doc: ExtractedDocument) -> list[ChunkDraft]: ...


    _CHUNKERS: dict[str, Chunker] = {
        "text/html": WebChunker(),
        "application/xhtml+xml": WebChunker(),
    }


    def chunker_for(mime_type: str) -> Chunker:
        """Raises NoChunkerError for a MIME type with no strategy."""
    ```

    - The MIME type is the only switch. `ExtractedDocument.mime_type` and `Document.mime_type` already exist, so there is no separate "source" flag.
    - There is no generic fallback chunker yet, because only HTML can arrive. A PDF extractor later returns an `ExtractedDocument` too (plan 008 decision 25) and registers `application/pdf` → `PdfChunker` here.
    - `chunker.name` and `chunker.version` are written to the document's `meta` and each chunk's `meta`. A later query can then find documents chunked by an older version.
    - Sizes are dataclass fields on the chunker, not env settings. They are part of the algorithm: a change should bump `version`, and an env var would let it drift silently.
14. **`ChunkDraft`** is what a chunker returns. The ingest service turns it into `Chunk` rows, adding `chunk_index` (0-based, in order), `document_id` and `collection_id`.

    ```python
    @dataclass(frozen=True)
    class ChunkDraft:
        content: str
        token_count: int
        heading_path: list[str]
        block_start: int  # range into ExtractedDocument.blocks this chunk came from
        block_end: int
    ```

    `Chunk.meta` = `{"heading_path": [...], "blocks": [start, end], "chunker": "web", "chunker_version": 1}`.
15. **Token counts are estimated, not exact.** `estimate_tokens(text) = ceil(len(text) / 4)`, in `chunking/tokens.py`. There is no tokenizer dependency and nothing to download or cache.
    - **Why an estimate is enough:** sizes only shape the chunks. The only hard limit is the embedding model's input (8,191 tokens for `text-embedding-3-small`), and `max_tokens` is 800, about 10× headroom. An estimate that is off by 2× changes the chunk sizes but breaks nothing. It also works the same for any embedding provider.
    - **Where it's off:** about 4 characters per token holds for English prose. Code and non-Latin scripts (CJK) use more tokens per character, so their chunks run larger than the estimate says. This is acceptable for web docs and well inside the headroom.
    - `chunks.token_count` stores the estimate. Real token counts for cost come from the embeddings API's `usage.total_tokens` (decision 22).
    - The chunker takes the counter as a constructor argument (`count_tokens: Callable[[str], int] = estimate_tokens`). Tests can pass a whitespace counter, and an exact tokenizer can be swapped in later without other changes.
    - **Rejected:** `tiktoken` and HuggingFace `tokenizers` both download encoding files on first use, which needs network access or a pre-warmed cache in the worker and Docker image. A word count × 1.3 is no more accurate, and worse on code and URLs.
16. **Rendering blocks as chunk text.** `content` is plain, lightly marked text, so an LLM reading it later can see the structure:
    - heading → `#` × level, a space, then the text
    - paragraph, quote → the text (quote prefixed `> `)
    - list → its items, one per line, prefixed `- ` (nesting indentation kept)
    - table → rows with cells joined by ` | `
    - code → the text in a fenced block

    Blocks are joined with a blank line. The heading breadcrumb is **not** in `content` (decision 20).
17. **`WebChunker` v1 algorithm.** Defaults: `target_tokens=400`, `max_tokens=800`, `min_tokens=100`, `overlap_tokens=60` (tuned in slice 5).
    1. **Units.** Walk `doc.sections` in order. Each section's blocks are rendered and counted. A section's `heading_path` comes from `Section.heading_path`.
    2. **Oversized blocks** (over `max_tokens`) are split into pieces first (decision 19). The pieces then behave like blocks.
    3. **Packing sections.** Keep a "current chunk". For the next section:
       - If it fits with the current chunk within `target_tokens`, **and** it is in the same branch (same `heading_path[0]`, or the current chunk is under `min_tokens`), append it. A merged chunk's `heading_path` is the longest common prefix of its sections' paths.
       - Otherwise, flush the current chunk and start a new one with this section.
    4. **Large sections** (over `target_tokens` on their own) are flushed separately and split greedily at block boundaries into pieces of at most `target_tokens` (one block may push a piece up to `max_tokens`). The heading block stays in the first piece. Every piece keeps the section's `heading_path`. From slice 3, each piece after the first starts with the overlap tail (decision 18).
    5. **Tiny tail.** A last piece under `min_tokens` is folded into the previous chunk of the same section if the result stays within `max_tokens`.
    6. Output order follows block order, so `chunk_index` order is reading order.

    In slice 2, steps 2 and the overlap are left out: an oversized block becomes its own chunk, even over `max_tokens`. Slice 3 adds both.
18. **Overlap: only inside a split section.**
    - When a large section is split, piece *n + 1* starts with the tail of piece *n*: whole trailing blocks if they fit in `overlap_tokens`, otherwise the trailing sentences of the last block, up to `overlap_tokens`. It is always whole sentences or blocks, never a cut through a word, so a chunk shown as a citation still reads well.
    - There is no overlap between sections or between merged-section chunks. A new heading means a new topic, and the `heading_path` gives the context. Overlap there mostly adds duplicate search hits.
    - The overlap tokens count toward the piece's size, so the `max_tokens` cap still holds.
    - 60 tokens on a 400-token target is about 15%, the usual range for prose.
19. **Splitting an oversized block, by type:**

    | Block | Split on | Notes |
    |-------|----------|-------|
    | paragraph, quote | Sentences | Regex on `.`, `!` or `?` followed by whitespace and an uppercase letter, digit or opening quote/bracket; no NLP dependency. Abbreviations ("e.g. The") may split early, which is acceptable |
    | list | Items | Groups of whole items |
    | table | Rows | The first row (the header, when present) is repeated at the top of each piece |
    | code | Lines | Groups of whole lines, each piece fenced again |
    | any piece still over `max_tokens` | Characters | Last resort: windows of `max_tokens × 4` characters, cut back to the last whitespace when there is one. Happens only for, say, one enormous line |

20. **The heading breadcrumb goes into the embedding input, not `content`.** `embedding_input(title, chunk)` returns:

    ```
    <document title>
    <heading_path joined with " > ">   (line omitted when the path is empty)

    <content>
    ```

    - This puts the page and section context into the vector, which helps short chunks like "Install it with pip" match "how to install X".
    - `content` stays clean for display and citations. Retrieval can prepend the same breadcrumb when it builds the LLM prompt.
    - The function is deterministic, so the input can always be rebuilt from stored data with no extra column. `token_count` counts `content` only.

### Embedding (`app/services/embedding/`)

21. **An `Embedder` protocol, with one OpenAI-compatible implementation used for OpenRouter (default) and OpenAI.**

    ```python
    class Embedder(Protocol):
        name: str  # "openrouter:openai/text-embedding-3-small", stored in document meta
        dimensions: int

        async def embed(self, texts: list[str]) -> EmbedResult: ...


    @dataclass(frozen=True)
    class EmbedResult:
        vectors: list[list[float]]  # same order as the input texts
        tokens: int | None  # billed input tokens reported by the provider, if any
        cost: float | None  # USD, when the provider reports it (OpenRouter does)


    class EmbeddingError(Exception):
        def __init__(self, message: str, *, retryable: bool = False): ...


    def get_embedder() -> Embedder:
        """By settings.embedding_provider: "openrouter" or "openai"."""
    ```

    - **One class, two providers.** OpenRouter's `POST /api/v1/embeddings` is OpenAI-compatible, and the architecture doc already prescribes `AsyncOpenAI` with a `base_url` for OpenRouter. So there is a single `OpenAICompatibleEmbedder` (`openai_compatible.py`; not `openai.py`, which would shadow the package) built as `openai.AsyncOpenAI(api_key=settings.embedding_api_key, base_url=<provider base url>, timeout=settings.embedding_timeout_seconds, max_retries=0)`.
      - `get_embedder()` uses `settings.embedding_base_url` when it's set. Otherwise the provider's default applies: `https://openrouter.ai/api/v1` for `openrouter`, and the SDK default for `openai`.
      - Switching between the two providers is a settings change only, but see "model ids" below.
      - Retrying is the task's job, as with the crawler, so retries don't multiply (`max_retries=0`). One client is created per task run, because Celery tasks have no lifespan.
    - **Model ids are provider-specific.** OpenRouter puts the vendor in front (`openai/text-embedding-3-small`), and OpenAI doesn't (`text-embedding-3-small`). The same underlying model gives the same vectors either way. Changing to a *different* model, however, needs a full re-embed, because vectors from two models can't be compared. `meta.embedding.model` records which model produced each document's vectors, so mixed collections can be detected.
    - **Dimensions are requested and checked.** Every request sends `dimensions=EMBEDDING_DIM` (1536). Every returned vector's length is checked, and a mismatch is a permanent `EmbeddingError` naming the model. A misconfigured model id then fails clearly instead of on the pgvector insert. `get_embedder()` also checks `embedder.dimensions == EMBEDDING_DIM`.
    - **Error mapping, by HTTP status** (OpenRouter's documented codes, which are a superset of OpenAI's):

      | Retryable | Permanent |
      |-----------|-----------|
      | 408, 429, 500, 502, 503, 504, 524, 529, timeouts and connection errors (`APITimeoutError`, `APIConnectionError`) | 400, 401, 403, 404, 413, **402** (out of OpenRouter credits), any other 4xx, an empty `embedding_api_key` |

      - A 402 error message says to add credits at openrouter.ai/credits, so the document's `error` explains itself.
      - A 413 says to lower `embedding_batch_size`.
    - **The response is checked defensively.** Vectors are matched to inputs by `index`. A response whose `data` has fewer or more vectors than inputs is a retryable `EmbeddingError`, because routers occasionally return incomplete payloads.
    - **Usage:** `EmbedResult.tokens` is `usage.total_tokens`, and `EmbedResult.cost` is OpenRouter's `usage.cost`, which is `None` on OpenAI. The SDK keeps unknown fields, so `cost` is read from the usage object's extra fields.
    - OpenRouter provider-routing options (`provider: {...}` via `extra_body`) are not set. The defaults route `openai/text-embedding-3-small` to the same model's hosts, which is fine.
22. **`embed_document(document_id, trace_id, attempt=0)` task** (`app/tasks/embedding.py`). The task is thin. The logic is `async def run_embedding(db, document_id, embedder)` in `app/services/embedding/__init__.py`, which is what the tests call:
    1. Load the document. If it's missing, log a WARNING and return. If it's `ready`, return (idempotent).
    2. Set `status = processing`, clear `error`, commit.
    3. Select chunks with `embedding IS NULL`, ordered by `chunk_index`. In batches of `embedding_batch_size`:
       - build the inputs (decision 20) and call `embed`,
       - write the vectors and add the batch's `tokens` and `cost` to running totals in `meta.embedding`,
       - **commit after each batch**.

       A retry then resumes where it stopped, without paying again for finished batches, and the totals still cover every batch.
    4. When none are left, set `status = ready` and finish `meta.embedding = {"model": embedder.name, "dimensions": 1536, "tokens": <sum>, "cost": <sum>}`, then commit.
       - Log `embedded document <id>: chunks=… batches=… tokens=… cost=… duration_ms=…`.
       - `tokens` is the exact billed count, unlike the estimated `chunks.token_count`. `tokens` and `cost` are left out when the provider doesn't report them.
    - A retryable `EmbeddingError` retries after **5 s, 15 s, then 60 s** (longer than the crawler's delays, because provider rate-limit windows are per minute). Attempts are counted in `attempt`, like `crawl_url`. The document stays `processing` meanwhile.
    - A permanent error, or retries exhausted: `status = failed`, `error = <message>`, a WARNING log, no re-raise.
    - A document stuck in `processing` because a worker died can be re-run by enqueuing `embed_document` again. An automatic sweeper is out of scope.
23. **Settings** (`app/core/config.py` and `.env.example`):

    | Setting | Default | Meaning |
    |---------|---------|---------|
    | `embedding_provider` | `"openrouter"` | `Literal["openrouter", "openai"]` |
    | `embedding_base_url` | `""` | Empty = the provider's default (`https://openrouter.ai/api/v1` for OpenRouter) |
    | `embedding_api_key` | `""` | OpenRouter (or OpenAI) key. Empty = every embed fails permanently with a clear error |
    | `embedding_model` | `"openai/text-embedding-3-small"` | Provider-specific id (`text-embedding-3-small` on OpenAI). Must produce `EMBEDDING_DIM` (1536) dimensions |
    | `embedding_batch_size` | `100` | Chunks per API call |
    | `embedding_timeout_seconds` | `30` | Per API call |

    The `EMBEDDING_DIM` comment in `app/db/types.py` changes to name the model as `openai/text-embedding-3-small` (via OpenRouter).

### Sync exceptions

24. **Chunking is CPU-bound** (regex sentence splitting, string building over a document of up to 5 MB), so `store_extracted` calls `await asyncio.to_thread(chunker.chunk, doc)`. It runs in the Celery worker, never on the API loop. Add `# SYNC-EXCEPTION: chunking is CPU-bound; called via asyncio.to_thread inside the Celery worker`, plus this row in the table:

    | Where | What | Why it can't be async | Isolation |
    |-------|------|-----------------------|-----------|
    | `app/services/chunking/` | Splitting an extracted document into chunks | CPU-bound pure-Python work; no I/O to await | Called through `asyncio.to_thread`; runs in the Celery worker |

    Embedding is async I/O (`AsyncOpenAI`) and needs no exception.

### Out of scope (recorded here)

25. - **Recrawl / update** of a changed page (decision 10 explains the gap).
    - **Retrieval:** search queries, an API endpoint, filtering on `ready`.
    - **Hybrid search:** a `tsvector` column for keyword search.
    - **Cross-page boilerplate:** footer or CTA text not marked up as chrome repeats in every page's chunks. A per-collection chunk-hash frequency check can come later.
    - **PDF and other chunkers,** and a generic fallback chunker.
    - **A sweeper** for documents stuck in `processing`.
    - **Following links.**
    - **Section anchors** (`#id` deep links) in chunk meta: the extractor doesn't capture heading ids yet.

## Code

Migration (`alembic revision -m "add document content"`):

```python
def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "content",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("documents", "content")
```

`app/models/document.py` (additions):

```python
from sqlalchemy.orm import deferred

    content_hash: Mapped[str] = mapped_column(String(64))  # sha256 of the normalised extracted text
    # the full ExtractedDocument; deferred so list queries don't load it
    content: Mapped[dict[str, Any] | None] = deferred(mapped_column(JSONType))
```

`app/services/ingest.py` (shape only):

```python
async def store_extracted(
    db: AsyncSession, collection_id: int, doc: ExtractedDocument
) -> StoreResult:
    """Insert a pending Document with its content and chunks, in one transaction."""
    if await db.get(Collection, collection_id) is None:
        return StoreResult(StoreOutcome.COLLECTION_MISSING)
    existing = await _find_by_hash(db, collection_id, doc.content_hash)
    if existing is not None:
        return StoreResult(StoreOutcome.DUPLICATE, existing.id, existing.status)
    chunker = chunking.chunker_for(doc.mime_type)
    # SYNC-EXCEPTION: chunking is CPU-bound; called via asyncio.to_thread
    drafts = await asyncio.to_thread(chunker.chunk, doc)
    document = Document(..., status=DocumentStatus.PENDING, content=doc.model_dump(...))
    document.chunks = [
        Chunk(collection_id=collection_id, chunk_index=i, content=d.content, ...)
        for i, d in enumerate(drafts)
    ]
    db.add(document)
    try:
        await db.commit()
    except IntegrityError:  # a concurrent task stored the same page
        await db.rollback()
        existing = await _find_by_hash(db, collection_id, doc.content_hash)
        return StoreResult(StoreOutcome.DUPLICATE, existing.id, existing.status)
    return StoreResult(StoreOutcome.STORED, document.id, chunks=len(drafts), tokens=...)
```

`app/tasks/crawler.py` (changes):

```python
@celery_app.task(bind=True, max_retries=None)
def crawl_url(
    self, url: str, trace_id: str, collection_id: int, attempt: int = 0, requeues: int = 0
) -> None:
    ...
            outcome, doc, stored = asyncio.run(_crawl_and_store(url, collection_id))
    ...
            raise self.retry(..., args=(url, trace_id, collection_id), kwargs={...})
    ...
        if stored.outcome is StoreOutcome.STORED or (
            stored.outcome is StoreOutcome.DUPLICATE and stored.status == DocumentStatus.PENDING
        ):
            embedding_tasks.embed_document.delay(stored.document_id, trace_id)


async def _crawl_and_store(url, collection_id):
    outcome, doc = await crawler_service.crawl_page(url)
    if doc is None:
        return outcome, None, None
    async with task_session() as db:
        return outcome, doc, await ingest.store_extracted(db, collection_id, doc)
```

`app/tasks/embedding.py`:

```python
RETRY_DELAYS = (5, 15, 60)  # seconds before failure retries 1, 2 and 3


@celery_app.task(bind=True, max_retries=None)
def embed_document(self, document_id: int, trace_id: str, attempt: int = 0) -> None:
    with logger.contextualize(trace_id=trace_id, job="embed_document"):
        try:
            # SYNC-EXCEPTION: Celery task bodies are sync; asyncio.run drives the async work
            asyncio.run(_run(document_id))
        except EmbeddingError as exc:
            if exc.retryable and attempt < len(RETRY_DELAYS):
                raise self.retry(
                    countdown=RETRY_DELAYS[attempt],
                    args=(document_id, trace_id),
                    kwargs={"attempt": attempt + 1},
                ) from exc
            asyncio.run(_mark_failed(document_id, str(exc)))
            logger.warning("embedding failed for document {}: {}", document_id, exc)
```

`app/cli/__main__.py` (additions):

```python
@app.command()
def create_collection(
    name: str, description: str | None = None, owner_email: str | None = None
) -> None:
    """Create a collection and print its id."""


@app.command()
def crawl_url(url: str, collection: int = typer.Option(..., help="Collection id")) -> None:
    """Queue a crawl of one web page into a collection."""


@app.command()
def show_chunks(document_id: int) -> None:
    """Print a document's chunks: index, tokens, heading path, content."""
```

## Files to create/modify

| File | Slice | Purpose |
|------|-------|---------|
| `alembic/versions/<rev>_add_document_content.py` (new) | 1 | `documents.content` column |
| `app/models/document.py` | 1 | `content` (deferred), `content_hash` comment |
| `app/services/ingest.py` (new) | 1, 2 | `store_extracted`, duplicate handling, chunk rows |
| `app/tasks/crawler.py` | 1, 4 | `collection_id` arg, store after extract, enqueue embedding |
| `app/cli/__main__.py` | 1, 2 | `create-collection`, `crawl-url --collection`, `show-chunks` |
| `pyproject.toml`, `uv.lock` | 4 | Add `openai` |
| `app/services/chunking/__init__.py` (new) | 2 | Registry, `chunker_for`, `NoChunkerError` |
| `app/services/chunking/base.py` (new) | 2 | `Chunker` protocol, `ChunkDraft`, rendering helpers |
| `app/services/chunking/tokens.py` (new) | 2 | `estimate_tokens` (characters ÷ 4) |
| `app/services/chunking/web.py` (new) | 2, 3 | `WebChunker` |
| `app/services/embedding/__init__.py` (new) | 4 | `get_embedder`, `embedding_input`, `run_embedding` |
| `app/services/embedding/base.py` (new) | 4 | `Embedder` protocol, `EmbeddingError` |
| `app/services/embedding/openai_compatible.py` (new) | 4 | `OpenAICompatibleEmbedder` (OpenRouter, OpenAI) |
| `app/tasks/embedding.py` (new) | 4 | `embed_document` task |
| `app/core/celery_app.py` | 4 | Add `app.tasks.embedding` to `include` |
| `app/core/config.py`, `.env.example` | 4 | Embedding settings |
| `app/db/types.py` | 4 | `EMBEDDING_DIM` comment names the OpenRouter model id |
| `docs/architecture/index.md` | 2 | Sync-exception row for chunking |
| `tests/unit/test_web_chunker.py` (new) | 2, 3 | Chunking rules |
| `tests/unit/test_cli_crawl.py`, `tests/unit/test_cli.py` | 1, 2 | `--collection`, `create-collection`, `show-chunks` |
| `tests/unit/test_crawler.py` | 1, 4 | Retry args, store outcomes, embed enqueue |
| `tests/integration/test_ingest.py` (new) | 1, 2 | `store_extracted` against SQLite |
| `tests/integration/test_embedding.py` (new) | 4 | `run_embedding` with a fake embedder |
| `tests/unit/test_embedding_task.py` (new) | 4 | Task retries and failure |
| `tests/unit/test_openai_compatible_embedder.py` (new) | 4 | Error mapping, ordering, dimensions, usage and cost, with `httpx.MockTransport` behind `AsyncOpenAI(http_client=...)` |
| `docs/wiki/ingestion.md` (new), `docs/wiki/web-crawl.md`, `docs/wiki/index.md` | 6 | Docs |

## Testing plan

No network, no Redis, no OpenRouter or OpenAI. Chunker tests inject a whitespace token counter (`len(text.split())`) so sizes are easy to reason about in assertions; one test pins `estimate_tokens` itself (`""` → 0, 4 characters → 1, 5 → 2). Embedding tests use a `FakeEmbedder` (fixed `dimensions=1536`, deterministic vectors, reports `tokens` and `cost` per batch, records each batch, can be told to raise). DB tests use the `db_session` SQLite fixture.

**Chunking** (`test_web_chunker.py`). Documents are built directly as `ExtractedDocument`s, with small sizes passed to `WebChunker(target_tokens=…, …)`:

- Small sibling sections are merged into one chunk, and the chunk's `heading_path` is their common prefix.
- Sections in different top-level branches are not merged, unless the current chunk is under `min_tokens`.
- A large section is split at block boundaries. The heading block is in the first piece, and every piece has the section's `heading_path`.
- A tiny last piece is folded into the previous one.
- **No lost text:** every block's text appears in at least one chunk's `content`. **No reordering:** the first occurrences follow block order.
- `block_start` / `block_end` match the source blocks. The output is deterministic (same input twice gives an equal result).
- Pre-heading content (`heading_path == []`) gets its own chunk or merges forward.
- Slice 3:
  - The overlap tail appears at the start of piece *n + 1* inside a split section, and is never on the first chunk of a section.
  - Every chunk is ≤ `max_tokens`, including oversized paragraph, list, table and code blocks.
  - The table header row is repeated in each table piece.
  - Code is split on line boundaries and every piece is fenced.
  - The sentence splitter keeps the punctuation and splits on `. The` but not `3.14`.
- Registry: `text/html` and `application/xhtml+xml` give `WebChunker`, and `application/pdf` raises `NoChunkerError`.
- `embedding_input` includes the title and the joined path, and leaves out the path line when it is empty.

**Ingest** (`test_ingest.py`):

- Stores a `pending` document with the mapped columns, `content` round-trips into an `ExtractedDocument`, and `meta` has the chunker name and version.
- Chunks are stored with contiguous `chunk_index`, `collection_id`, `token_count`, meta, and `embedding` NULL.
- The same hash in the same collection returns `DUPLICATE` with the existing id and status, and inserts nothing. The same hash in another collection is stored.
- A missing collection returns `COLLECTION_MISSING`.
- A chunker exception stores nothing.

**Embedding** (`test_embedding.py`, `test_embedding_task.py`, `test_openai_compatible_embedder.py`):

- `run_embedding` fills every embedding, sets `ready` and `meta.embedding` (including the summed `tokens`), and calls the embedder in `ceil(n / batch_size)` batches with the breadcrumb inputs.
- Resume: chunks that already have embeddings are not sent again, and the `tokens` / `cost` totals from the earlier run are kept and added to.
- An already `ready` document makes no embedder call. A missing document logs a WARNING.
- Task: a retryable error at `attempt` 0, 1 and 2 retries with countdowns 5, 15 and 60. At 3 it marks `failed` with `error` and logs a WARNING. A permanent error fails at once.
- `OpenAICompatibleEmbedder`, with OpenRouter-shaped responses:
  - 429, 500, 502, 503, 524 and 529 raise retryable errors.
  - 400, 401, 402 (message mentions credits), 413 and an empty API key raise permanent errors.
  - Vectors come back in input order even when the response `data` is shuffled.
  - A response with too few vectors is retryable; a vector of the wrong length is permanent.
  - Each request sends `dimensions=1536` and the configured model id to the configured base URL.
  - `tokens` comes from `usage.total_tokens` and `cost` from `usage.cost`; `cost` is `None` when it is missing (OpenAI-shaped response).
- `get_embedder()`: `openrouter` with an empty `embedding_base_url` uses `https://openrouter.ai/api/v1`; an explicit `embedding_base_url` wins.

**Crawl task and CLI:**

- Retry and re-queue calls pass `args=(url, trace_id, collection_id)`.
- `STORED` enqueues `embed_document` once. `DUPLICATE` with `pending` re-enqueues it. `DUPLICATE` with `ready` and `COLLECTION_MISSING` don't, and the last one logs a WARNING.
- `crawl-url` without `--collection` fails. With an unknown id it exits 1 and enqueues nothing. With a known id it enqueues `(url, trace_id, id)`. The collection check is monkeypatched.
- `create-collection` prints the id. With an unknown `--owner-email` it exits 1. With a known one it creates an owner membership.
- `show-chunks` prints chunks in order, and exits 1 for an unknown document.

## Verification

- `make test` and `make format` are clean.
- `make migrate`, then `uv run cli create-collection docs --owner-email admin@example.com` prints an id.
- With Redis and `make worker` running: `uv run cli crawl-url https://docs.python.org/3/tutorial/ --collection <id>`.
  - Slice 1: the worker logs `stored document <n>`, and the `documents` row is `pending` with `content` filled. Crawling the same URL again logs `duplicate of document <n>`.
  - Slices 2–3: `uv run cli show-chunks <n>` shows chunks in reading order. They follow headings, no chunk is over `max_tokens`, overlap appears only inside long sections, and tables keep their header.
  - Slice 4 (with `EMBEDDING_API_KEY` set to an OpenRouter key): the worker logs `embedded document <n>` with tokens and cost (check the cost against the OpenRouter activity page), the document is `ready`, and `select count(*) from chunks where document_id = <n> and embedding is null` returns 0. As a manual check, a nearest-neighbour query (`order by embedding <=> (select embedding from chunks where id = <x>) limit 5`) returns chunks from the same topic.
  - With an empty `EMBEDDING_API_KEY`, the document becomes `failed` with a clear `error`, and the chunks remain.
  - With `EMBEDDING_MODEL` set to a model that doesn't exist, the document becomes `failed` with the provider's 404 or 400 message.
- Slice 5: crawl 3–5 different real sites (docs, a blog, a marketing page), review the chunks together, and record the final sizes in the wiki.
- Known limits:
  - A changed page becomes a second document (no recrawl handling).
  - Boilerplate that isn't marked up as chrome repeats across pages.
  - The sentence splitter is heuristic.
  - Token counts in `chunks.token_count` are estimates (characters ÷ 4). Code and CJK text produce chunks larger than the estimate; exact billed tokens are in `documents.meta.embedding.tokens`.
  - A document stuck in `processing` needs a manual re-enqueue.
