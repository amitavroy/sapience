# Add trace id to every request and log line (GH-3)

## To-do

Each slice ends in a working, reviewable state. Pause for review after each slice.

| # | Slice | Step | Done |
|---|-------|------|------|
| 1 | Trace id on requests | `trusted_proxies` setting in `config.py` (+ parsed networks helper) and `TRUSTED_PROXIES=` in `.env.example` | [x] |
| 1 | Trace id on requests | `app/core/trace.py`: `trace_id` ContextVar, `resolve_trace_id(request)` | [x] |
| 1 | Trace id on requests | `request_log.py`: resolve id, `logger.contextualize`, `X-Request-ID` response header, `client_request_id` for untrusted header | [x] |
| 1 | Trace id on requests | Tests: generated id in header, untrusted header ignored, trusted header adopted, invalid value replaced, CIDR/comma parsing | [x] |
| 2 | Trace id in every log line | `logger.py`: default `trace_id` extra, trace id in format; human format when `debug`, JSON otherwise | [x] |
| 2 | Trace id in every log line | Test: all records from one request share the same `trace_id` | [x] |
| 3 | CLI + docs | Fresh trace id per CLI invocation in `app/cli/__main__.py` | [x] |
| 3 | CLI + docs | Wiki "Logging / trace id" note (incl. uvicorn `--forwarded-allow-ips`, proxy overwrites client header, job pattern for later) | [x] |

## Context

Logging is a plain loguru one-liner per request (`app/middleware/request_log.py`, sink in `app/core/logger.py`). Lines from one request can't be correlated, and background jobs (not built yet) will need the same id. Goal: one trace id per request on every log line, echoed to the client, adoptable from a trusted proxy, ready to be passed into jobs later.

## Decisions

1. **Server owns the id:** default `uuid4().hex`. A client can't be trusted to send unique or safe ids.
2. **Trusted adoption:** incoming `X-Request-ID` is used only if `request.client.host` (the real socket peer) is within `TRUSTED_PROXIES` and the value fully matches `[A-Za-z0-9-]{8,64}`. Otherwise a new id is generated.
3. **Config:** `TRUSTED_PROXIES` is a comma-separated string in `.env` (IPs or CIDRs; bare IP becomes /32 or /128). Split on `,`, strip blanks, parse with `ipaddress.ip_network(..., strict=False)`, once (cached). Empty default = trust nobody.
4. **Untrusted header:** logged once as `client_request_id` on the request log line, trimmed to 64 chars.
5. **Response header:** final id returned as `X-Request-ID`.
6. **Propagation:** ContextVar `trace_id` plus `logger.contextualize(trace_id=...)`. Works across `await`; no new dependency. OpenTelemetry deferred.
7. **Format:** `logger.configure(extra={"trace_id": "-"})` so lines outside a request still format. Human-readable with trace id when `debug`; `serialize=True` JSON otherwise.
8. **CLI:** each invocation gets its own trace id.
9. **Jobs (later):** when a runner is added, pass `trace_id` as a job argument and wrap execution in `logger.contextualize(trace_id=..., job=name)`. Not built now (no jobs exist).
10. **Deployment note:** if uvicorn runs with `--proxy-headers`, keep `--forwarded-allow-ips` equal to `TRUSTED_PROXIES`; the edge proxy should overwrite any client-supplied `X-Request-ID`.

## Files to create/modify

| File | Slice | Purpose |
|------|-------|---------|
| `app/core/config.py`, `.env.example` | 1 | `trusted_proxies` setting and parsed networks |
| `app/core/trace.py` (new) | 1 | ContextVar, `resolve_trace_id` |
| `app/middleware/request_log.py` | 1 | Resolve, contextualize, header, `client_request_id` |
| `tests/test_trace.py` (new) | 1, 2 | Header and log-correlation tests |
| `app/core/logger.py` | 2 | Format with trace id, JSON in prod |
| `app/cli/__main__.py` | 3 | Trace id per invocation |
| `docs/wiki/index.md` | 3 | Logging note |

## Testing plan

- httpx ASGI transport with a controllable client IP (`ASGITransport(client=(ip, port))`), `TRUSTED_PROXIES` patched per test.
- Cases: no header; header from untrusted peer ignored (and logged as `client_request_id`); header from trusted peer adopted; invalid/too-short/too-long value from trusted peer replaced; comma-separated list and CIDR parsing; empty setting trusts nobody.
- Loguru sink capturing records: every record emitted during one request has the same `trace_id`; a record outside a request has `"-"`.

## Verification

- `make test` and `make format` are clean.
- `make dev`, then `curl -i localhost:8000/health`: response has `X-Request-ID` and the same id appears in the log line.
- With `TRUSTED_PROXIES=127.0.0.1`: `curl -H "X-Request-ID: abc12345" -i localhost:8000/health` echoes `abc12345`; with it unset, a fresh id is returned.
- Known risk: behind a proxy, `request.client.host` is the proxy only if uvicorn proxy-headers handling is configured consistently (decision 10).
