# Crawl a web page: extraction service, Celery task and CLI (GH-3)

## To-do

Each slice ends in a working, reviewable state. Pause for review after each slice. From slice 1 on, `python -m app.cli crawl-url <url>` works end to end and the result appears in the worker log.

| # | Slice | Step | Done |
|---|-------|------|------|
| 1 | End-to-end skeleton | Add `selectolax` (`uv add selectolax`) | [x] |
| 1 | End-to-end skeleton | Settings: `crawler_user_agent`, `crawler_timeout_seconds`, `crawler_max_bytes` in `app/core/config.py` and `.env.example` | [x] |
| 1 | End-to-end skeleton | `app/schemas/extracted_document.py`: minimal `ExtractedDocument` and `Block` (paragraph blocks only) | [x] |
| 1 | End-to-end skeleton | `app/services/web_extractor.py`: single fetch (stream, size cap, content type, charset decoding), noise stripping, block walk emitting paragraphs, `EMPTY_CONTENT` | [x] |
| 1 | End-to-end skeleton | `app/tasks/crawler.py`: `crawl_url` task logging a summary (INFO) and the full JSON (DEBUG); register it in `celery_app.include` | [x] |
| 1 | End-to-end skeleton | `app/cli/__main__.py`: `crawl-url <url>` command that enqueues the task | [x] |
| 1 | End-to-end skeleton | `SYNC-EXCEPTION` comment and a row in `docs/architecture/index.md` | [x] |
| 1 | End-to-end skeleton | Tests and fixtures: `with_scripts`, `plain_markup`, `javascript_app`, `empty_body`, `latin1_meta_charset`; size cap, content type; CLI enqueues; task logs the summary | [x] |
| 2 | Failures and retries | `ExtractionError` with `reason`, `status_code` and `retryable`. 500, timeouts and connection errors are retryable; all other 4xx and 5xx are not | [ ] |
| 2 | Failures and retries | Task retries retryable errors after 3 s, 5 s and 15 s (3 retries); permanent and exhausted failures logged at WARNING | [ ] |
| 2 | Failures and retries | Tests: 500 then success, 404 and 503 not retried, retries exhausted, timeout retried, logged lines | [ ] |
| 3 | Politeness | `app/services/crawler.py`: per-host rate limit (`crawler_rate_limit`, default `1/second`) via the Redis limiter; the task re-queues when limited | [ ] |
| 3 | Politeness | robots.txt check (RFC 9309 rules, `*` group), cached per host in the worker process; disallowed URLs skipped with a log line | [ ] |
| 3 | Politeness | Tests: limited then allowed re-queues without using a failure retry; robots allow, disallow, 404 and 5xx cases | [ ] |
| 4 | Typed blocks and sections | Heading, list, table, code, quote block types; `figcaption`; `sections` as index ranges with `heading_path`; `title` fallback | [ ] |
| 4 | Typed blocks and sections | Tests and fixtures: `structured`, `nested_blocks` (no duplicated or lost text), skipped heading levels, pre-heading content | [ ] |
| 5 | Links and hash | `links` (absolute, filtered, deduped, internal flag, `<base href>`), `content_hash` over the normalised text | [ ] |
| 5 | Links and hash | Tests: link rules, hash stable across markup changes, changes with text | [ ] |
| 6 | Tune on real pages | Run `crawl-url` on a few real static sites with `LOG_FILE_LEVEL=DEBUG`, review the JSON together, adjust the structure | [ ] |
| 7 | Docs | Wiki entry: the CLI command, the task, the output structure, rate limit, robots.txt and limits; note the new dependency | [ ] |

## Context

Sapience will ingest website content. This ticket delivers a single-page crawl: you run `python -m app.cli crawl-url <url>`, which enqueues a Celery task. The task checks robots.txt, waits for the per-domain rate limit, fetches the page, extracts structured content and logs a summary. Failures are retried.

Following links (a multi-page crawl), persistence to `Document` and `Chunk` (plan 004) and an API endpoint are later tickets. The output structure is not settled yet, so slice 6 tunes it against real pages before anything depends on it.

Codebase facts that shape the design:

- Python 3.12, uv, async FastAPI. Services are module-level async functions (`app/services/google_chat.py`), not classes.
- `httpx` is already a dependency. The lifespan creates `httpx.AsyncClient(timeout=10)` (`app/main.py:20`) for the Google token verifier. It does not follow redirects.
- **Celery** (`app/core/celery_app.py`):
  - The `include=[...]` list is explicit.
  - `task_acks_late=True`, so tasks must be idempotent.
  - `task_ignore_result=True`.
  - Task bodies are sync and run async code with `asyncio.run`, inside `logger.contextualize(trace_id=..., job=...)` (`app/tasks/google_chat.py`).
- **Rate limiting** (`app/core/limiter.py`) uses `limits.aio`'s `FixedWindowRateLimiter` on Redis. The coredis client only works inside `async with redis:`.
- **CLI** (`app/cli/__main__.py`) is Typer. The callback sets one trace id per invocation, and commands are sync.
- `docs/architecture/index.md` requires an explicit timeout and a retry policy for outbound calls (line 23). CPU-bound work must not run directly in `async def`, and sync work needs a `# SYNC-EXCEPTION:` comment and a row in the table (lines 28-54).
- Settings live in `app/core/config.py` (pydantic-settings), and each new setting goes in `.env.example`.
- Outbound HTTP is mocked in tests with `httpx.MockTransport` (see `JwksServer` in `tests/`). Logging is loguru via `app.core.logger`.

## Decisions

### Flow

1. **The CLI is the entry point.** `python -m app.cli crawl-url <url>` validates that the scheme is http or https, calls `crawl_url.delay(url, trace_id)` and prints `queued: <url> (trace <id>)`. It does not wait for the result. The trace id from the CLI callback travels with the task, so you can match the CLI line to the worker's log lines.
2. **The task is thin, the service holds the logic.**
   - `app/tasks/crawler.py`: `crawl_url` is a bound task. Its sync body calls `asyncio.run(crawler_service.crawl_page(url))` inside `logger.contextualize(trace_id=..., job="crawl_url")`, and handles retries and re-queues.
   - `app/services/crawler.py`: `crawl_page(url)` creates the `httpx.AsyncClient`, checks robots.txt, acquires the rate limit, then calls `web_extractor.extract_url`.
   - `app/services/web_extractor.py`: fetching and extraction, with no Celery or Redis knowledge.
3. **The output is a log only.** On success the task logs one INFO line with: the URL, `source_uri`, status, title, number of blocks, sections and links, text length, `content_hash` and duration in ms. It also logs the full `ExtractedDocument` JSON at DEBUG, for tuning (slice 6). Nothing is persisted.
4. **Idempotency.** With `acks_late`, a task may run twice. A single-page, log-only crawl has no side effects beyond logs, so a duplicate run is harmless.

### Fetching (`web_extractor`)

5. **`httpx`, with options set per request.** The service takes an `httpx.AsyncClient` and passes `timeout`, `follow_redirects=True` and headers on each request, so a shared client's defaults are never changed. The crawler service creates one client per task run, because Celery tasks have no lifespan.
6. **Settings, not constants** (`app/core/config.py` and `.env.example`):
   - `crawler_user_agent`: a real desktop Chrome UA. The default is `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36`. Bump it to the current stable Chrome version at implementation time.
   - `crawler_timeout_seconds: float = 15`.
   - `crawler_max_bytes: int = 5 * 1024 * 1024`.
   - `crawler_rate_limit: str = "1/second"`, per host, in `limits` syntax.
   - `crawler_robots_cache_seconds: int = 3600`.
   - Requests also send browser-like `Accept: text/html,application/xhtml+xml;q=0.9,*/*;q=0.8` and `Accept-Language: en-US,en;q=0.9` headers. httpx handles gzip and brotli.
7. **The size cap is enforced while streaming.**
   - First, reject early if `Content-Length` exceeds the cap.
   - Then read with `client.stream()` and `aiter_bytes()`, counting bytes and aborting past the cap with `TOO_LARGE`.
   - The counted bytes are decompressed, so a small compressed response that expands to a huge one is also caught.
   - Reading the whole body first was rejected: it holds the full response in worker memory before the check runs.
8. **Content type.**
   - Accept `text/html` and `application/xhtml+xml`.
   - If the header is missing, sniff the first 1 KB for `<!doctype html` or `<html` (case-insensitive, after whitespace).
   - Anything else raises `NOT_HTML`.
   - `mime_type` is stored lowercased, without parameters.
9. **Character decoding is our own, from bytes:**
   1. the charset in the `Content-Type` header,
   2. otherwise `<meta charset>` or `<meta http-equiv="Content-Type">` in the first 2 KB,
   3. otherwise UTF-8 with `errors="replace"`.

   httpx's `response.text` only uses the header, which garbles pages that declare their charset only in a `<meta>` tag.
10. **Status codes.** Redirects are followed. Any final 4xx or 5xx raises `HTTP_STATUS` with the status code, so error pages are never extracted as content. Only **500** is retryable for now. Every other 4xx and 5xx (including 429, 502, 503 and 504) fails immediately. Gateway errors (502 to 504) are often transient, so they are the first candidates to add later.
11. **Errors carry a reason.** The service makes **one attempt** and raises `ExtractionError(reason, message, status_code=None, retryable=False)`. It does no retrying itself (see decision 12).

    | Reason | Raised for | Retryable |
    |--------|------------|-----------|
    | `INVALID_URL` | A scheme other than http or https | No |
    | `HTTP_STATUS` | A final 4xx or 5xx | Only for 500 |
    | `NETWORK` | `httpx.TransportError`: timeouts, connection errors | Yes |
    | `TOO_LARGE` | Over `crawler_max_bytes` | No |
    | `NOT_HTML` | Content type not HTML | No |
    | `EMPTY_CONTENT` | The walk produced no blocks | No |

### Retries and politeness (task and `crawler` service)

12. **Retries live in the Celery task, not the service.** Retrying with `asyncio.sleep` in the service would hold a worker slot for up to about 83 s, mostly idle. It would also be lost if the worker restarted, and it would multiply with any retries at the task level. With `self.retry(countdown=...)` the task goes back on the queue and frees the worker.
    - Policy: 3 retries after the first attempt, waiting **3 s, then 5 s, then 15 s**. These are fixed delays, `RETRY_DELAYS = (3, 5, 15)`.
    - Failure attempts are counted in an explicit `attempt` task argument, not in `self.request.retries`, because rate-limit re-queues (decision 13) also go through `self.retry` and must not use up the failure budget. The task is declared with `max_retries=None`, and the bounds are enforced in code.
    - `self.retry` must be raised in the sync task body, outside `asyncio.run`. The async service raises `ExtractionError` or `RateLimited`, and the task catches them.
    - A non-retryable failure, or a retryable one with no retries left, is logged at WARNING with the URL, reason, status code and attempt count. The task then returns without re-raising: nothing reads results (`task_ignore_result`), so re-raising would only add a stack trace to the log.
    - This retry policy is how this ticket meets the architecture doc's "timeout and retry policy" rule for outbound calls.
13. **Per-host rate limit through the existing Redis limiter.** Celery's own `rate_limit=` task option applies per worker, so it can't enforce a per-domain limit across several workers.
    - Use `limits.aio`'s `FixedWindowRateLimiter` on `RedisStorage(settings.redis_url)`, with the key `crawler:<host>` (host lowercased) and `parse(settings.crawler_rate_limit)`.
    - The robots.txt fetch also counts against the limit, because it is a request to the same host.
    - When a hit is refused, the service raises `RateLimited`. The task then re-queues itself with `self.retry(countdown=random.uniform(1, 3), kwargs=<same attempt>)`. The jitter stops many queued tasks for one host from retrying in lockstep.
    - After 60 re-queues (a counter in the task kwargs), the task gives up with a WARNING. That only happens if a host is flooded with tasks.
    - **Risk to check in slice 3:** the coredis client is created at import and is entered with `async with` per event loop. Each task run uses a fresh `asyncio.run` loop, so verify that re-entering the client across loops works. If it doesn't, build the `RedisStorage` inside `crawl_page`. The limiter backend is reached through one small helper, `_acquire(host)`, so tests can monkeypatch it without Redis.
14. **robots.txt, following RFC 9309.**
    - Fetch `<scheme>://<host>/robots.txt` with the same client, user agent and timeout. Parse it with the stdlib `urllib.robotparser.RobotFileParser.parse()`, and check `can_fetch("*", url)`.
    - We follow the `*` group only. With a browser user agent we don't match any named bot group. Whether to identify as a named bot (for example `SapienceBot`) is decided in the multi-page crawl ticket.
    - A 4xx response for robots.txt means everything is allowed. A 5xx or network error means everything is disallowed, per the RFC: the URL is skipped and logged, not retried, because the server is unhealthy. Redirects are followed.
    - A disallowed URL is not an error. The task logs `skipped: disallowed by robots.txt` at INFO and returns.
    - The parsed result is cached per host in the worker process (a module-level dict with an expiry of `crawler_robots_cache_seconds`). A Redis cache shared across workers can come with the multi-page crawl if it is needed.

### Extraction

15. **Parsing with `selectolax`** (Lexbor backend, `selectolax.lexbor`). It is fast and has a small API (`css()`, `decompose()`, `.text()`), with node traversal for the block walk. The rejected alternatives are:
    - `beautifulsoup4` + `lxml`, which is slower.
    - `trafilatura` or `readability`, which guess the "main content", while the requirement is the whole body.
    - Scrapy, which is a framework that fights the Celery and async design.
    - Playwright, which is only needed for JS-rendered pages and is out of scope.
16. **Parsing runs in `asyncio.to_thread`, flagged as a sync exception.** selectolax has no async API, so `extract()` is a plain sync function called through `asyncio.to_thread`. The architecture doc notes that threads help little with CPU work because of the GIL. This is acceptable because the caller is now the Celery worker, which is off the API's event loop. `app/core/security.py` sets the precedent for small CPU work through `to_thread`.

    Add `# SYNC-EXCEPTION: selectolax has no async API; parsing runs via asyncio.to_thread inside the Celery worker`, plus this row in the table:

    | Where | What | Why it can't be async | Isolation |
    |-------|------|-----------------------|-----------|
    | `app/services/web_extractor.py` | HTML parsing and block extraction with selectolax | CPU-bound; selectolax has no async API | Called through `asyncio.to_thread`; runs in the Celery worker |

17. **Scope of extraction.** Only `<body>` produces blocks. `<head>` and `<html lang>` are read for metadata only: title, description, canonical URL, language and `og:*` tags.
18. **Noise removed from the body before the walk:**
    - Tags removed with their contents: `script`, `style`, `noscript`, `template`, `iframe`, `svg`, `canvas`, `link`, `meta`, `input`, `select`, `option`, `textarea` and `button`.
    - Any element with a `hidden` attribute or `aria-hidden="true"`.
    - HTML comments (a test proves comment text never reaches the output).
    - `<form>` itself is **not** removed, only its controls. Some sites (ASP.NET, for example) wrap the whole page in one form.
    - Inline `style="display:none"` and CSS-class hiding are not detected, which is a known limit.
    - Image `alt` text is dropped. `figcaption` is kept.
19. **Block walk ("leaf block wins, loose inline text becomes a paragraph").** This is a recursive walk of the body in document order. It avoids both duplicated text (a `<p>` inside an `<li>`) and lost text (text sitting directly in a `<div>`).
    - **Block elements are emitted once, whole, and not recursed into:**
      - `h1`–`h6` → `heading` (with `level`).
      - `p` and `figcaption` → `paragraph`.
      - `ul` and `ol` → `list`. Its `items` are the text of each `li`. A nested list's items are flattened into the parent list, prefixed with two spaces per depth level.
      - `table` → `table`. Its `rows` are the `th` and `td` text per `tr`.
      - `pre` → `code`.
      - `blockquote` → `quote`, whose text includes any `<p>` children.
    - **Containers are recursed into:** `div`, `section`, `article`, `main`, `header`, `footer`, `nav`, `aside`, `figure`, `form`, `dl`, `details`, and any unknown tag.
      - Between block children, runs of inline content (bare text, `a`, `span`, `strong`, `em`, inline `code`, `br`, and so on) are gathered into a `paragraph`.
      - `dt` and `dd` text is gathered the same way.
    - **Whitespace:**
      - Text in all blocks except `code` is collapsed to single spaces and stripped.
      - `br` becomes a single space inside a paragraph.
      - `code` blocks keep their whitespace exactly.
      - Empty blocks are dropped.
    - In slice 1 every block type is emitted as `paragraph`, using the same walk. Slice 4 adds the specific types.
20. **Sections.** A section starts at each heading block. Headings use a stack: on a heading of level N, pop entries of level ≥ N, then push it. Its `heading_path` is the stack's texts.
    - Skipped levels (an `h1` followed directly by an `h3`) simply nest.
    - A second `h1` resets the path.
    - Content before the first heading forms a section with `heading_path = []`.
    - Headings inside navigation or the footer also create sections. This is accepted for now, in line with the whole-body decision.
21. **`title`** falls back through `<title>`, then `og:title`, then the first `h1` block, then `source_uri`. It is a top-level field and never empty, because `Document.title` is required.
22. **Empty content.** If the walk produces no blocks, the service raises `EMPTY_CONTENT` and the task logs it at WARNING. JS-rendered shells (an empty `<div id="root">` plus scripts) hit this case. Without it, every empty page would share one hash and collide on `(collection_id, content_hash)` once we persist.

### Output and storage efficiency

23. **No duplicated content in the model.**
    - `blocks` is the only place text is stored.
    - `sections` hold index ranges (`start`, `end` into `blocks`) plus `heading_path`, not copies of blocks. The heading text isn't repeated either, because it is `heading_path[-1]` and `blocks[start]`.
    - `text` is a method, `text()`, that isn't serialized.
    - `list` blocks store only `items`, and `table` blocks only `rows`.
    - Dump with `model_dump(exclude_defaults=True)` so empty fields aren't written.
24. **Fetch fields are top-level and optional** (`None` for non-web sources later): `requested_url`, `status_code` and `fetched_at`. `source_uri` is the **final URL after redirects**. There is no separate `final_url` field, since that would duplicate `source_uri`. `metadata` holds the remaining source-specific keys: description, language, canonical URL and og tags.
25. **The model is source-neutral**, so PDF, DOCX and TXT extractors can return the same shape later. `links` is web-only and defaults to empty.

### Links

26. **Rules:**
    - Resolve each `<a href>` against `<head><base href>` when present, otherwise against `source_uri`.
    - Keep only `http` and `https` links. That drops `mailto:`, `tel:`, `javascript:`, `data:` and fragment-only links.
    - Strip the `#fragment`.
    - Dedupe by `href`, keeping the first non-empty link text.
    - `internal` means the host matches `source_uri`'s host, case-insensitively, after removing a leading `www.`. Other subdomains count as external.
    - Links are collected after noise removal.
    - Links are output only in this ticket. Following them is the multi-page crawl ticket.

### Hash

27. **`content_hash` = sha256 hex of the normalised `text()`.** No title or metadata is included.
    - `text()` joins blocks with `\n\n`:
      - heading, paragraph and quote blocks contribute their text,
      - lists contribute items joined by `\n`, each prefixed `- `,
      - tables contribute rows with cells joined by ` | ` and rows joined by `\n`,
      - code contributes its text verbatim.
    - Before hashing, the text is Unicode NFC-normalised and encoded as UTF-8.
    - The result is always 64 characters and fits `String(64)`. It costs a few milliseconds even for 5 MB.
    - Changing the walk or the `text()` format changes every hash. That is acceptable before persistence exists, but must be noted as a breaking change afterwards.
    - Known effect: a footer that changes (the year, "latest posts") changes the hash. That is accepted with the whole-body decision.

### Later tickets (recorded here)

28. **Persistence: no staging table and no separate content table.** The extraction will be saved on the existing `Document` row (status `pending`, then `processing`, then `ready` or `failed`).
    - It goes in one nullable JSON column mapped with SQLAlchemy `deferred()`, so list queries don't load it. Postgres TOAST stores large values out of line and compresses them.
    - The full extraction is stored, not just the chunks, so we can re-chunk or re-embed without re-fetching.
    - Split it into a separate table only if we need multiple extractions per document, very large files, or object storage.
    - The `Document.content_hash` comment ("raw content") gets updated then.
29. **Out of scope:**
    - Following links (multi-page crawl, depth and page limits, a visited set).
    - Persistence.
    - SSRF protection (needed when exposed via an API).
    - JS rendering.
    - File uploads.
    - An identifying bot user agent.
    - A shared Redis robots cache.

## Code

`app/schemas/extracted_document.py` (the final shape after slice 5; slice 1 ships `paragraph` blocks only, with no sections or links):

```python
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

BlockType = Literal["heading", "paragraph", "list", "table", "code", "quote"]


class Block(BaseModel):
    type: BlockType
    text: str = ""  # heading, paragraph, code, quote
    level: int | None = None  # heading only
    items: list[str] = Field(default_factory=list)  # list only
    rows: list[list[str]] = Field(default_factory=list)  # table only


class Section(BaseModel):
    heading_path: list[str]  # [] for content before the first heading
    start: int  # blocks[start:end]; blocks[start] is the heading when there is one
    end: int


class Link(BaseModel):
    href: str  # absolute, no fragment
    text: str
    internal: bool


class ExtractedDocument(BaseModel):
    source_uri: str  # final URL after redirects
    title: str
    mime_type: str  # no parameters, e.g. "text/html"
    content_hash: str  # sha256 of normalised text(), maps to Document.content_hash
    requested_url: str | None = None
    status_code: int | None = None
    fetched_at: datetime | None = None
    metadata: dict[str, Any] = Field(
        default_factory=dict
    )  # description, language, canonical_url, og
    blocks: list[Block]
    sections: list[Section] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)  # web only

    def text(self) -> str: ...

    def section_blocks(self, section: Section) -> list[Block]:
        return self.blocks[section.start : section.end]
```

`app/services/web_extractor.py` (shape only):

```python
class ExtractionErrorReason(StrEnum):
    INVALID_URL = "invalid_url"
    HTTP_STATUS = "http_status"
    NETWORK = "network"
    TOO_LARGE = "too_large"
    NOT_HTML = "not_html"
    EMPTY_CONTENT = "empty_content"


class ExtractionError(Exception):
    def __init__(self, reason, message, *, status_code=None, retryable=False): ...


@dataclass(frozen=True)
class FetchedPage:
    requested_url: str
    final_url: str
    status_code: int
    mime_type: str
    body: bytes
    fetched_at: datetime


async def fetch_page(client: httpx.AsyncClient, url: str) -> FetchedPage:
    """One GET: validate the scheme, stream with the size cap, check status and content type."""


def extract(page: FetchedPage) -> ExtractedDocument:
    """Sync and pure: decode, strip noise, walk blocks, build sections, links and hash."""
    # SYNC-EXCEPTION: selectolax has no async API; called via asyncio.to_thread


async def extract_url(client: httpx.AsyncClient, url: str) -> ExtractedDocument:
    page = await fetch_page(client, url)
    return await asyncio.to_thread(extract, page)
```

`app/services/crawler.py` (shape only):

```python
class RateLimited(Exception): ...


class CrawlOutcome(StrEnum):
    EXTRACTED = "extracted"
    ROBOTS_DISALLOWED = "robots_disallowed"


async def _acquire(host: str) -> bool:
    """One hit on the per-host Redis limiter; True if allowed."""


async def _robots_allows(client: httpx.AsyncClient, url: str) -> bool:
    """RFC 9309 semantics; parsed robots.txt cached per host in-process."""


async def crawl_page(url: str) -> tuple[CrawlOutcome, ExtractedDocument | None]:
    """robots.txt -> rate limit -> extract. Raises RateLimited or ExtractionError."""
```

`app/tasks/crawler.py`:

```python
RETRY_DELAYS = (3, 5, 15)  # seconds before failure retries 1, 2 and 3
MAX_RATE_LIMIT_REQUEUES = 60


@celery_app.task(bind=True, max_retries=None)  # bounds enforced below
def crawl_url(self, url: str, trace_id: str, attempt: int = 0, requeues: int = 0) -> None:
    with logger.contextualize(trace_id=trace_id, job="crawl_url"):
        try:
            # SYNC-EXCEPTION: Celery task bodies are sync; asyncio.run drives the async work
            outcome, doc = asyncio.run(crawler_service.crawl_page(url))
        except crawler_service.RateLimited:
            if requeues >= MAX_RATE_LIMIT_REQUEUES:
                logger.warning("giving up on {}: rate limited {} times", url, requeues)
                return
            raise self.retry(
                countdown=random.uniform(1, 3),
                kwargs={
                    "url": url,
                    "trace_id": trace_id,
                    "attempt": attempt,
                    "requeues": requeues + 1,
                },
            )
        except ExtractionError as exc:
            if exc.retryable and attempt < len(RETRY_DELAYS):
                logger.info("retrying {} in {}s: {}", url, RETRY_DELAYS[attempt], exc.reason)
                raise self.retry(
                    countdown=RETRY_DELAYS[attempt],
                    kwargs={
                        "url": url,
                        "trace_id": trace_id,
                        "attempt": attempt + 1,
                        "requeues": requeues,
                    },
                )
            logger.warning("crawl failed for {}: {} (status {}, attempts {})", ...)
            return
        ...  # log the summary at INFO (or the robots skip), and the full JSON at DEBUG
```

`app/cli/__main__.py`:

```python
@app.command()
def crawl_url(url: str) -> None:
    """Queue a crawl of one web page; results appear in the worker log."""
    if urlsplit(url).scheme not in ("http", "https"):
        typer.echo("url must start with http:// or https://", err=True)
        raise typer.Exit(1)
    crawler_tasks.crawl_url.delay(url, trace_id.get())
    typer.echo(f"queued: {url} (trace {trace_id.get()})")
```

## Files to create/modify

| File | Slice | Purpose |
|------|-------|---------|
| `pyproject.toml`, `uv.lock` | 1 | Add `selectolax` |
| `app/core/config.py`, `.env.example` | 1, 3 | Crawler settings (UA, timeout, max bytes, rate limit, robots cache) |
| `app/schemas/extracted_document.py` (new) | 1, 4, 5 | Output models |
| `app/services/web_extractor.py` (new) | 1, 2, 4, 5 | Fetch and extract |
| `app/services/crawler.py` (new) | 1, 3 | robots.txt, rate limit, orchestration |
| `app/tasks/crawler.py` (new) | 1, 2, 3 | `crawl_url` task, retries, re-queues, logging |
| `app/core/celery_app.py` | 1 | Add `app.tasks.crawler` to `include` |
| `app/cli/__main__.py` | 1 | `crawl-url` command |
| `docs/architecture/index.md` | 1 | Sync-exception row |
| `tests/unit/test_web_extractor.py` (new) | 1, 2, 4, 5 | Extraction and fetch tests |
| `tests/unit/test_crawler.py` (new) | 1, 2, 3 | Task, retries, rate limit, robots tests |
| `tests/unit/test_cli_crawl.py` (new) | 1 | CLI tests |
| `tests/fixtures/pages/*.html` (new) | 1, 4 | HTML samples |
| `docs/wiki/index.md` | 7 | Crawl command, task, output, limits |

## Testing plan

All tests use `httpx.MockTransport` and fixture files, with no network access and no Redis. The limiter is reached only through `crawler._acquire`, which tests monkeypatch. Log lines are captured with the existing loguru `logs` fixture pattern (`tests/unit/test_google_chat_task.py`).

**Fixture pages** (`tests/fixtures/pages/`):

| Fixture | What it contains | What the test asserts |
|---------|------------------|-----------------------|
| `with_scripts.html` | `<script>` in head and body (inline and `src`), `<style>`, `<noscript>`, an HTML comment, an `aria-hidden` element, a `<select>` with options, a `<button>` | None of that text appears in any block or in `text()`; the visible text around it does |
| `plain_markup.html` | Text directly in `<div>` and `<span>`, `<br>`, no `<p>` or headings | All text is kept as paragraph blocks, in order |
| `javascript_app.html` | SPA shell: `<div id="root"></div>` plus bundle scripts | Raises `EMPTY_CONTENT`; the task logs a warning and does not retry |
| `empty_body.html` | `<body></body>` and whitespace only | Raises `EMPTY_CONTENT`; logged |
| `structured.html` | Proper `h1`/`h2`/`h3`, `p`, `ul` with a nested `ol`, `table`, `pre`, `blockquote`, `figure`/`figcaption`, `<head>` with title, description, canonical, og tags and `<html lang>` | Correct block types and order; `heading_path` per section; `code` keeps its whitespace; `figcaption` is kept; metadata is filled; head text is not in blocks |
| `nested_blocks.html` | `<p>` inside `<li>`, `<p>` inside `<blockquote>`, a `div` with text and a `<p>` side by side, a skipped heading level, text before the first heading | No text is duplicated or lost; skipped levels nest; the pre-heading section has `heading_path == []` |
| `latin1_meta_charset.html` | ISO-8859-1 bytes, charset declared only in `<meta>` | Accented characters decode correctly |

**Fetch and error classification** (`test_web_extractor.py`):

- A redirect sets `source_uri` to the final URL and `requested_url` to the original.
- `Content-Length` over the cap, and a streamed body over the cap without `Content-Length`, both raise `TOO_LARGE`.
- `application/pdf` raises `NOT_HTML`. A missing content type with an HTML body is accepted. `mime_type` has no parameters.
- `ftp://` raises `INVALID_URL`.
- A 500 raises `HTTP_STATUS` with `retryable=True`. A 404 and a 503 raise with `retryable=False`.
- Timeouts and connection errors raise `NETWORK` with `retryable=True`.
- Links: relative links resolve, `<base href>` wins, `mailto:`, `tel:`, `javascript:` and `#top` are dropped, fragments are stripped, duplicates removed, `www.` counts as internal and other subdomains don't.
- Hash: the same text in different markup gives the same hash, a one-word change gives a different hash, and it is 64 hex characters.

**Task, retries and politeness** (`test_crawler.py`). `crawl_url.retry` is monkeypatched to record its `countdown` and `kwargs` and raise `celery.exceptions.Retry`, and the task is called directly.

- Success logs the summary line at INFO and the JSON at DEBUG.
- A retryable error at `attempt=0`, `1` and `2` retries with countdowns of 3, 5 and 15 and an increasing `attempt`. At `attempt=3` it logs a WARNING and does not retry.
- A non-retryable error (404, 503, `EMPTY_CONTENT`) logs a WARNING and does not retry.
- `RateLimited` re-queues with a countdown between 1 and 3 and `requeues + 1`, while `attempt` stays the same. At `MAX_RATE_LIMIT_REQUEUES` it gives up with a WARNING.
- robots.txt:
  - A disallowed path is skipped and logged at INFO, and the page is never fetched.
  - An allowed path is fetched.
  - A 404 robots.txt allows everything.
  - A 500 robots.txt disallows everything.
  - A second call for the same host uses the cache, so robots.txt is fetched once.
- The rate limit is requested for both the robots.txt fetch and the page fetch.

**CLI** (`test_cli_crawl.py`, Typer `CliRunner`, with `crawl_url.delay` monkeypatched):

- A valid URL enqueues one task with the URL and a trace id, and prints `queued:`.
- `ftp://x` or `not-a-url` exits with code 1 and enqueues nothing.

## Verification

- `make test` and `make format` are clean.
- Start Redis, run `make worker`, and run `uv run python -m app.cli crawl-url https://docs.python.org/3/tutorial/`. The CLI prints the queued line with a trace id. The worker logs the summary under the same trace id, and with `LOG_FILE_LEVEL=DEBUG` the full JSON: no script text, sensible sections, absolute links, a 64-character hash, no duplicated text.
- Queue the same URL 5 times quickly. The worker log shows rate-limit re-queues, and fetches spaced about 1 s apart.
- Crawl a URL disallowed by its site's robots.txt. It logs `skipped: disallowed by robots.txt`.
- Crawl a URL that returns 404 (logged, no retry) and one on a host that refuses connections (retried after 3 s, 5 s and 15 s, then logged as failed).
- Review the structure together after slice 6, and adjust the models before the docs slice.
- Known limits:
  - JS-rendered pages raise `EMPTY_CONTENT`.
  - Inline `display:none` and CSS-hidden content are not detected.
  - Navigation and footer text is included in blocks and the hash.
  - Only the robots.txt `*` group is honoured.
