import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from app.core.logger import logger
from app.core.trace import resolve_trace_id, trace_id


async def log_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    tid = resolve_trace_id(request)
    # an id from an untrusted client is not used, but kept in the log for correlation
    incoming = request.headers.get("x-request-id", "")[:64]
    client_id = f" client_request_id={incoming}" if incoming and incoming != tid else ""
    token = trace_id.set(tid)
    try:
        with logger.contextualize(trace_id=tid):
            start = time.perf_counter()
            response = await call_next(request)
            ms = (time.perf_counter() - start) * 1000
            response.headers["X-Request-ID"] = tid
            logger.info(
                f"{request.method} {request.url.path} {response.status_code} {ms:.1f}ms{client_id}"
            )
    finally:
        trace_id.reset(token)
    return response
