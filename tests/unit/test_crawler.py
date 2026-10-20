from pathlib import Path

import httpx
import pytest
from celery.exceptions import Retry

from app.core.logger import logger
from app.services import crawler as crawler_service
from app.tasks import crawler as crawler_tasks

PAGES = Path(__file__).parent.parent / "fixtures" / "pages"
REAL_CLIENT = httpx.AsyncClient
HTML = {"content-type": "text/html"}


@pytest.fixture
def logs() -> list[dict]:
    """Records of everything logged at DEBUG and above during the test."""
    records: list[dict] = []
    sink = logger.add(lambda m: records.append(m.record), level="DEBUG")
    yield records
    logger.remove(sink)


@pytest.fixture(autouse=True)
def rate_limit_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """No Redis in tests: the per-host limiter always allows."""

    async def allow(_host: str) -> bool:
        return True

    monkeypatch.setattr(crawler_service, "_acquire", allow)


@pytest.fixture
def serve(monkeypatch: pytest.MonkeyPatch):
    """Make the task's HTTP client answer every request with the given response."""

    def _serve(response: httpx.Response) -> None:
        transport = httpx.MockTransport(lambda _: response)
        monkeypatch.setattr(
            crawler_service.httpx, "AsyncClient", lambda: REAL_CLIENT(transport=transport)
        )

    return _serve


def test_success_logs_the_summary_at_info_and_the_json_at_debug(logs: list[dict], serve) -> None:
    html = (PAGES / "with_scripts.html").read_bytes()
    serve(httpx.Response(200, content=html, headers={"content-type": "text/html"}))

    # sync test: the task drives its async body with asyncio.run, like the real worker
    crawler_tasks.crawl_url("https://a.test/p", "trace1234")

    [summary] = [r for r in logs if r["level"].name == "INFO"]
    assert summary["message"].startswith("crawled https://a.test/p source_uri=https://a.test/p")
    assert "title='Scripts page'" in summary["message"]
    assert "blocks=2" in summary["message"]
    assert summary["extra"] == {"trace_id": "trace1234", "job": "crawl_url"}
    [debug] = [r for r in logs if r["level"].name == "DEBUG"]
    assert debug["message"].startswith("extracted document: {")
    assert "Visible before" in debug["message"]


def test_failure_logs_a_warning_without_raising(logs: list[dict], serve) -> None:
    html = (PAGES / "javascript_app.html").read_bytes()
    serve(httpx.Response(200, content=html, headers={"content-type": "text/html"}))

    crawler_tasks.crawl_url("https://a.test/app", "trace1234")

    [warning] = [r for r in logs if r["level"].name == "WARNING"]
    assert "empty_content" in warning["message"]
    assert [r for r in logs if r["level"].name == "INFO"] == []


@pytest.fixture
def retries(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Record task.retry calls instead of talking to a broker; raises Retry like the real one."""
    calls: list[dict] = []

    def fake_retry(*, countdown: int, kwargs: dict) -> None:
        calls.append({"countdown": countdown, **kwargs})
        raise Retry()

    monkeypatch.setattr(crawler_tasks.crawl_url, "retry", fake_retry)
    return calls


def serve_handler(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        crawler_service.httpx, "AsyncClient", lambda: REAL_CLIENT(transport=transport)
    )


def warnings(logs: list[dict]) -> list[str]:
    return [r["message"] for r in logs if r["level"].name == "WARNING"]


def test_500_retries_after_3_seconds_then_the_retry_succeeds(
    logs: list[dict], retries: list[dict], monkeypatch: pytest.MonkeyPatch
) -> None:
    responses = iter([httpx.Response(500), httpx.Response(200, content=b"<p>hi</p>", headers=HTML)])
    serve_handler(monkeypatch, lambda _: next(responses))

    with pytest.raises(Retry):
        crawler_tasks.crawl_url("https://a.test/p", "trace1234")
    assert retries == [
        {
            "countdown": 3,
            "url": "https://a.test/p",
            "trace_id": "trace1234",
            "attempt": 1,
            "requeues": 0,
        }
    ]

    crawler_tasks.crawl_url("https://a.test/p", "trace1234", attempt=1)  # what the broker re-runs

    assert [r["message"] for r in logs if r["level"].name == "INFO"][0] == (
        "retrying https://a.test/p in 3s: http_status"
    )
    assert any(r["message"].startswith("crawled ") for r in logs)
    assert warnings(logs) == []


def test_retry_delays_are_3_5_and_15_seconds_with_a_rising_attempt(
    retries: list[dict], monkeypatch: pytest.MonkeyPatch
) -> None:
    serve_handler(monkeypatch, lambda _: httpx.Response(500))

    for attempt in range(3):
        with pytest.raises(Retry):
            crawler_tasks.crawl_url("https://a.test/p", "t", attempt=attempt)

    assert [(c["countdown"], c["attempt"]) for c in retries] == [(3, 1), (5, 2), (15, 3)]


def test_retries_exhausted_logs_a_warning_and_stops(
    logs: list[dict], retries: list[dict], monkeypatch: pytest.MonkeyPatch
) -> None:
    serve_handler(monkeypatch, lambda _: httpx.Response(500))

    crawler_tasks.crawl_url("https://a.test/p", "t", attempt=3)

    assert retries == []
    assert warnings(logs) == [
        "crawl failed for https://a.test/p: http_status (status 500, attempts 4)"
    ]


@pytest.mark.parametrize("status", [404, 503])
def test_other_error_statuses_are_not_retried(
    logs: list[dict], retries: list[dict], monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    serve_handler(monkeypatch, lambda _: httpx.Response(status))

    crawler_tasks.crawl_url("https://a.test/p", "t")

    assert retries == []
    assert warnings(logs) == [
        f"crawl failed for https://a.test/p: http_status (status {status}, attempts 1)"
    ]


def test_timeout_is_retried(retries: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    serve_handler(monkeypatch, timeout)

    with pytest.raises(Retry):
        crawler_tasks.crawl_url("https://a.test/p", "t")

    assert [(c["countdown"], c["attempt"]) for c in retries] == [(3, 1)]


def test_empty_content_is_not_retried(logs: list[dict], retries: list[dict], serve) -> None:
    serve(httpx.Response(200, content=(PAGES / "empty_body.html").read_bytes(), headers=HTML))

    crawler_tasks.crawl_url("https://a.test/p", "t")

    assert retries == []
    assert warnings(logs) == [
        "crawl failed for https://a.test/p: empty_content (status None, attempts 1)"
    ]
