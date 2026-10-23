# Web page crawl

`uv run cli crawl-url <url> --collection <id>` queues a crawl of one web page into a collection. It prints `queued: <url> (trace <id>)` and returns; the result appears in the worker log under that trace id. Only `http` and `https` URLs are accepted, and the collection must exist (exit code 1 otherwise). After extraction the page is stored, chunked and embedded: see [ingestion.md](ingestion.md). Links are collected but not followed.

    CLI → crawl_url task → robots.txt → per-host rate limit → fetch → extract → store + chunk → embed_document

- **Task:** `crawl_url` (`app/tasks/crawler.py`, arguments `url`, `trace_id`, `collection_id`) stores the page, enqueues `embed_document` and logs one INFO line (`crawled <url> source_uri=… status=… title=… blocks=… sections=… links=… text_length=… content_hash=… duration_ms=…`) and the full `ExtractedDocument` JSON at DEBUG. Set `LOG_FILE_LEVEL=DEBUG` to see the JSON in the log file.
- **Code:** the task is thin. `app/services/crawler.py` does robots.txt and the rate limit, and `app/services/web_extractor.py` fetches and extracts. The parser is `selectolax` (new dependency).
- **Fetch:** one GET with a browser user agent, following redirects. Any final 4xx or 5xx is an error, never extracted. Only `text/html` and `application/xhtml+xml` are accepted (a missing content type is sniffed). The body is read as a stream and cut off at `CRAWLER_MAX_BYTES`, counted after decompression. Charset comes from the header, then `<meta>`, then UTF-8.

## Output

`ExtractedDocument` (`app/schemas/extracted_document.py`):

| Field | Meaning |
|-------|---------|
| `source_uri` | Final URL after redirects; `requested_url`, `status_code` and `fetched_at` are separate fields |
| `title` | `<title>`, else `og:title`, else the first `h1`, else `source_uri` |
| `metadata` | `description`, `language`, `canonical_url`, `og` (only what the page has) |
| `blocks` | The text, in order. Types: `heading` (with `level`), `paragraph`, `list` (`items`), `table` (`rows`), `code`, `quote` |
| `sections` | Index ranges into `blocks` (`start`, `end`) with a `heading_path`; no text is repeated |
| `links` | Absolute `http(s)` links with `text` and an `internal` flag |
| `content_hash` | sha256 of the normalised text, 64 hex characters |

- Only `<body>` produces blocks. Scripts, styles, form controls, comments and `hidden` / `aria-hidden` content are dropped, and so is page chrome: `nav`, `aside`, and page-level `header` and `footer` (also `role="navigation"`, `complementary`, `banner`, `contentinfo`). Inside an `article`, `section` or `main`, a `header` or `footer` is kept.
- Nested lists are flattened into one `list` block, indented two spaces per level. `code` keeps its whitespace; everything else is collapsed.
- A section starts at each heading. A skipped level (`h1` then `h3`) just nests, a second `h1` resets the path, and content before the first heading has `heading_path == []`.
- Links are resolved against `<base href>` when present, deduped by `href`, and stripped of `#fragment`. `mailto:`, `tel:`, `javascript:`, `data:` and fragment-only links are dropped. `internal` means the same host as `source_uri`, ignoring case and a leading `www.`; other subdomains are external.
- `content_hash` covers the text only, not the title or metadata. Changing how blocks are built changes every hash.
- A page with no blocks (for example a JavaScript-rendered shell) fails with `EMPTY_CONTENT`.

## Politeness and retries

- **Rate limit:** `CRAWLER_RATE_LIMIT` (default `1/second`) per host, shared by all workers through Redis. The robots.txt request counts too. A limited task re-queues itself after 1 to 3 seconds and gives up with a WARNING after 60 re-queues. Re-queues do not use up the failure retries.
- **robots.txt:** checked before every page, `*` group only (RFC 9309). A 4xx means everything is allowed; a 5xx or a network error means everything is disallowed, with a WARNING and no retry. A disallowed page logs `skipped: disallowed by robots.txt (<url>)` at INFO. The parsed file is cached per host in each worker for `CRAWLER_ROBOTS_CACHE_SECONDS` (default 3600).
- **Retries:** only a final HTTP 500 and network errors (timeouts, connection failures) are retried, after 3 s, 5 s and 15 s. Every other 4xx and 5xx, and `TOO_LARGE`, `NOT_HTML` and `EMPTY_CONTENT`, fail at once. Permanent and exhausted failures log a WARNING with the reason, status code and attempt count.

## Settings

| Variable | Default | Meaning |
|----------|---------|---------|
| `CRAWLER_USER_AGENT` | desktop Chrome string | Sent on every request, including robots.txt |
| `CRAWLER_TIMEOUT_SECONDS` | `15` | Per request |
| `CRAWLER_MAX_BYTES` | `5242880` | Cap on the decompressed body |
| `CRAWLER_RATE_LIMIT` | `1/second` | Per host, `limits` syntax |
| `CRAWLER_ROBOTS_CACHE_SECONDS` | `3600` | Per host, per worker process |

## Known limits

- JavaScript-rendered pages are not supported (they fail with `EMPTY_CONTENT`).
- Hidden content set with inline `style="display:none"` or a CSS class is not detected, and chrome that is not marked up with a tag or ARIA role (`<div class="sidebar">`, a "Jump to content" link) is still included.
- Only the robots.txt `*` group is honoured, and there is no SSRF protection yet, so the command is for trusted local use.
