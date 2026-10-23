# Ingestion: store, chunk, embed

A crawled page is stored as a `pending` document with its chunks, then embedded in a second task. Retrieval (search) comes later.

    crawl_url ── extract ── store Document + chunks (one transaction, status=pending, embedding NULL)
              └─ enqueue embed_document(document_id)
    embed_document ── status=processing ── batches of chunks → embeddings (commit per batch) ── status=ready

Saving first and embedding afterwards means a failed embedding call retries only the embed step: the page is never fetched or chunked again. Chunks are embedded about 100 per API call, and changing the chunker or the embedding model later only needs the stored data.

## Commands

    uv run cli create-collection <name> [--description TEXT] [--owner-email EMAIL]   # prints the id
    uv run cli crawl-url <url> --collection <id>                                     # queues a crawl
    uv run cli show-chunks <document-id>                                             # index, tokens, heading path, content

`--owner-email` must belong to an existing user (exit code 1 otherwise) and adds an `owner` membership. `crawl-url` exits with code 1 if the collection does not exist, and enqueues nothing.

## Statuses

| Status | Meaning |
|--------|---------|
| `pending` | Stored and chunked, waiting for embeddings |
| `processing` | `embed_document` is running (or died mid-run) |
| `ready` | Every chunk has an embedding |
| `failed` | Embedding failed permanently; `error` says why. Chunks stay, so it can be retried |

A crawl or chunking failure stores nothing (the transaction rolls back), so no document is `failed` because of the crawl. Retrieval should filter on `documents.status = 'ready'`.

## Storing (`app/services/ingest.py`)

- `store_extracted(db, collection_id, doc)` inserts a `pending` `Document` and its `Chunk` rows in one transaction. The outcome is `STORED`, `DUPLICATE` or `COLLECTION_MISSING`; the crawl task logs `stored document <id> chunks=… tokens=…`, `duplicate of document <id>` or `collection <id> not found`.
- The full extraction is kept in `documents.content` (JSON, deferred so list queries don't load it). `meta` holds the page metadata plus `requested_url`, `status_code`, `fetched_at`, `chunker` and `chunker_version`.
- A document with the same `content_hash` in the same collection is a duplicate: nothing is stored. A `pending` duplicate gets `embed_document` enqueued again, which covers a worker that died after the commit. The same page in another collection is stored.
- `uploaded_by_id` stays NULL for CLI crawls.

## Chunking (`app/services/chunking/`)

A strategy per source type, chosen by MIME type (`chunker_for`). `text/html` and `application/xhtml+xml` use `WebChunker`; any other type raises `NoChunkerError`. `chunker` and `chunker_version` are recorded on the document and on every chunk.

`WebChunker` (version 2) defaults, as an estimated token count:

| Size | Default | Role |
|------|---------|------|
| `target_tokens` | 400 | Aim for chunks of about this size |
| `max_tokens` | 800 | Hard cap; the embedding model's limit is 8,191 |
| `min_tokens` | 100 | Under this a chunk is "tiny" and gets merged |
| `overlap_tokens` | 60 | Tail repeated between pieces of one split section |

Rules:

- **Rendering:** blocks become lightly marked text (`#` headings, `- ` list items, `> ` quotes, ` | ` table cells, fenced code), joined by a blank line. The heading breadcrumb is not in `content`.
- **Merging:** small sections in the same top-level branch are packed into one chunk up to `target_tokens`; the merged chunk's `heading_path` is the common prefix. A chunk under `min_tokens` may grow up to `max_tokens` and may merge across branches.
- **Splitting:** a section over `target_tokens` is split at block boundaries. The heading stays with the block after it, and every piece keeps the section's `heading_path`. A piece under `min_tokens` takes the next block instead of being cut off. A tiny tail is folded back if the result stays within `max_tokens`.
- **Tiny lead chunk:** a tiny chunk before a large section (navigation, byline) leads that section's first piece, which keeps the large section's heading path.
- **Overlap:** only inside a split section, never between sections. Whole trailing blocks, or trailing sentences, up to `overlap_tokens`.
- **Oversized blocks** (over `max_tokens`) are split: paragraphs and quotes by sentence, lists by item, tables by row with the header row repeated, code by line, and as a last resort by characters.
- **Token counts** are estimates: `ceil(characters / 4)`. Code and CJK text run larger than the estimate; this is fine because `max_tokens` leaves about 10× headroom under the embedding limit.

Chunking is CPU-bound, so `store_extracted` runs it through `asyncio.to_thread` inside the Celery worker (flagged `SYNC-EXCEPTION`, with a row in `docs/architecture/index.md`).

Sizes were checked on four real pages (a corporate blog, a security blog, a personal article, a marketing blog): chunks came out at roughly 170–480 tokens, none over the cap. Bump `WebChunker.version` whenever the output for the same input changes.

## Embedding (`app/services/embedding/`)

- **Embedder:** one `OpenAICompatibleEmbedder` (`openai.AsyncOpenAI`, `max_retries=0`) serves OpenRouter (default) and OpenAI. Switching providers is a settings change, but model ids differ (`openai/text-embedding-3-small` on OpenRouter, `text-embedding-3-small` on OpenAI). Every request sends `dimensions=1536` and each returned vector is length-checked.
- **Input:** `embedding_input(title, chunk)` is the document title, the `heading_path` joined with ` > ` (omitted when empty), a blank line, then the content. The breadcrumb goes into the vector, not into `content`.
- **Task:** `embed_document(document_id, trace_id)` sets `processing`, embeds chunks that have no vector in batches of `EMBEDDING_BATCH_SIZE` and commits after each batch, then sets `ready`. A retry resumes where it stopped. An already `ready` document is a no-op.
- **Result:** `documents.meta.embedding` holds `model`, `dimensions` and the summed billed `tokens` and `cost` (left out when the provider doesn't report them). The worker logs `embedded document <id>: chunks=… batches=… tokens=… cost=… duration_ms=…`.
- **Crawl hand-off:** `crawl_url` enqueues `embed_document` after a store, and again for a `pending` duplicate.

| Retryable (5 s, 15 s, then 60 s) | Permanent (`failed`, `error` set) |
|-----------------------------------|-----------------------------------|
| 408, 429, 500, 502, 503, 504, 524, 529, timeouts, connection errors, an incomplete response | 400, 401, 402 (out of OpenRouter credits), 403, 404, 413 (lower the batch size), any other 4xx, a wrong vector length, an empty API key |

## Settings

| Variable | Default | Meaning |
|----------|---------|---------|
| `EMBEDDING_PROVIDER` | `openrouter` | `openrouter` or `openai` |
| `EMBEDDING_BASE_URL` | empty | Empty = the provider's default (`https://openrouter.ai/api/v1` for OpenRouter) |
| `EMBEDDING_API_KEY` | empty | Empty = every embed fails permanently with a clear error |
| `EMBEDDING_MODEL` | `openai/text-embedding-3-small` | Provider-specific id; must give 1536 dimensions |
| `EMBEDDING_BATCH_SIZE` | `100` | Chunks per API call |
| `EMBEDDING_TIMEOUT_SECONDS` | `30` | Per API call |

## Known limits

- A changed page at the same URL has a new hash, so it becomes a second document. There is no recrawl handling yet.
- Boilerplate that is not marked up as page chrome (related posts, newsletter and promo blocks) is chunked and embedded like content.
- The extractor does not emit `<pre>` as `code` blocks, and a promo heading can become the `heading_path` of a whole article.
- The sentence splitter is heuristic; abbreviations may split early.
- A document stuck in `processing` (worker died) needs `embed_document` enqueued again by hand. There is no sweeper.
- Changing the chunker or the embedding model does not touch existing documents; there is no re-chunk or re-embed command yet. `meta.chunker_version` and `meta.embedding.model` show which documents are out of date.
