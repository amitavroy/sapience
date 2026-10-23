from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from celery.exceptions import Retry

from app.core.logger import logger
from app.services import crawler as crawler_service
from app.services import ingest
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


@pytest.fixture(autouse=True)
def robots_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests answer every request with one page; robots.txt has its own tests."""

    async def allow(_client: httpx.AsyncClient, _url: str) -> bool:
        return True

    monkeypatch.setattr(crawler_service, "_robots_allows", allow)


@pytest.fixture(autouse=True)
def store_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    """No database in these tests: storing the page always succeeds."""

    async def store(_db, _collection_id, _doc) -> ingest.StoreResult:
        return ingest.StoreResult(ingest.StoreOutcome.STORED, 7)

    @asynccontextmanager
    async def session():
        yield None

    monkeypatch.setattr(ingest, "store_extracted", store)
    monkeypatch.setattr(ingest, "task_session", session)


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
    crawler_tasks.crawl_url("https://a.test/p", "trace1234", 1)

    [summary] = [r for r in logs if r["message"].startswith("crawled ")]
    assert summary["message"].startswith("crawled https://a.test/p source_uri=https://a.test/p")
    assert "title='Scripts page'" in summary["message"]
    assert "blocks=2 sections=1 links=0 text_length=" in summary["message"]
    assert summary["extra"] == {"trace_id": "trace1234", "job": "crawl_url"}
    [debug] = [r for r in logs if r["level"].name == "DEBUG"]
    assert debug["message"].startswith("extracted document: {")
    assert "Visible before" in debug["message"]


def test_failure_logs_a_warning_without_raising(logs: list[dict], serve) -> None:
    html = (PAGES / "javascript_app.html").read_bytes()
    serve(httpx.Response(200, content=html, headers={"content-type": "text/html"}))

    crawler_tasks.crawl_url("https://a.test/app", "trace1234", 1)

    [warning] = [r for r in logs if r["level"].name == "WARNING"]
    assert "empty_content" in warning["message"]
    assert [r for r in logs if r["level"].name == "INFO"] == []


@pytest.fixture
def retries(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Record task.retry calls instead of talking to a broker; raises Retry like the real one."""
    calls: list[dict] = []

    def fake_retry(*, countdown: int, args: tuple, kwargs: dict) -> None:
        # like Celery, the retried call is args + kwargs, so none of them may repeat
        assert set(kwargs) == {"attempt", "requeues"}
        url, trace_id, collection_id = args
        calls.append(
            {
                "countdown": countdown,
                "url": url,
                "trace_id": trace_id,
                "collection_id": collection_id,
                **kwargs,
            }
        )
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
        crawler_tasks.crawl_url("https://a.test/p", "trace1234", 1)
    assert retries == [
        {
            "countdown": 3,
            "url": "https://a.test/p",
            "trace_id": "trace1234",
            "collection_id": 1,
            "attempt": 1,
            "requeues": 0,
        }
    ]

    crawler_tasks.crawl_url(
        "https://a.test/p", "trace1234", 1, attempt=1
    )  # what the broker re-runs

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
            crawler_tasks.crawl_url("https://a.test/p", "t", 1, attempt=attempt)

    assert [(c["countdown"], c["attempt"]) for c in retries] == [(3, 1), (5, 2), (15, 3)]


def test_retries_exhausted_logs_a_warning_and_stops(
    logs: list[dict], retries: list[dict], monkeypatch: pytest.MonkeyPatch
) -> None:
    serve_handler(monkeypatch, lambda _: httpx.Response(500))

    crawler_tasks.crawl_url("https://a.test/p", "t", 1, attempt=3)

    assert retries == []
    assert warnings(logs) == [
        "crawl failed for https://a.test/p: http_status (status 500, attempts 4)"
    ]


@pytest.mark.parametrize("status", [404, 503])
def test_other_error_statuses_are_not_retried(
    logs: list[dict], retries: list[dict], monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    serve_handler(monkeypatch, lambda _: httpx.Response(status))

    crawler_tasks.crawl_url("https://a.test/p", "t", 1)

    assert retries == []
    assert warnings(logs) == [
        f"crawl failed for https://a.test/p: http_status (status {status}, attempts 1)"
    ]


def test_timeout_is_retried(retries: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    serve_handler(monkeypatch, timeout)

    with pytest.raises(Retry):
        crawler_tasks.crawl_url("https://a.test/p", "t", 1)

    assert [(c["countdown"], c["attempt"]) for c in retries] == [(3, 1)]


def test_empty_content_is_not_retried(logs: list[dict], retries: list[dict], serve) -> None:
    serve(httpx.Response(200, content=(PAGES / "empty_body.html").read_bytes(), headers=HTML))

    crawler_tasks.crawl_url("https://a.test/p", "t", 1)

    assert retries == []
    assert warnings(logs) == [
        "crawl failed for https://a.test/p: empty_content (status None, attempts 1)"
    ]


def deny_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    async def deny(_host: str) -> bool:
        return False

    monkeypatch.setattr(crawler_service, "_acquire", deny)


def test_rate_limited_requeues_with_jitter_and_keeps_the_failure_attempt(
    retries: list[dict], serve, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(httpx.Response(200, content=b"<p>hi</p>", headers=HTML))
    deny_rate_limit(monkeypatch)

    with pytest.raises(Retry):
        crawler_tasks.crawl_url("https://a.test/p", "t", 1, attempt=2, requeues=5)

    [call] = retries
    assert 1 <= call["countdown"] <= 3
    assert (call["attempt"], call["requeues"]) == (2, 6)


def test_limited_then_allowed_runs_without_using_a_failure_retry(
    logs: list[dict], retries: list[dict], serve, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(httpx.Response(200, content=b"<p>hi</p>", headers=HTML))
    deny_rate_limit(monkeypatch)
    with pytest.raises(Retry):
        crawler_tasks.crawl_url("https://a.test/p", "t", 1)
    [requeue] = retries

    async def allow(_host: str) -> bool:
        return True

    monkeypatch.setattr(crawler_service, "_acquire", allow)  # the re-queued run gets through
    crawler_tasks.crawl_url(
        "https://a.test/p", "t", 1, attempt=requeue["attempt"], requeues=requeue["requeues"]
    )

    assert requeue["attempt"] == 0  # the failure budget is untouched
    assert any(r["message"].startswith("crawled ") for r in logs)
    assert warnings(logs) == []


def test_gives_up_after_the_maximum_number_of_requeues(
    logs: list[dict], retries: list[dict], serve, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(httpx.Response(200, content=b"<p>hi</p>", headers=HTML))
    deny_rate_limit(monkeypatch)

    crawler_tasks.crawl_url(
        "https://a.test/p", "t", 1, requeues=crawler_tasks.MAX_RATE_LIMIT_REQUEUES
    )

    assert retries == []
    assert warnings(logs) == ["giving up on https://a.test/p: rate limited 60 times"]


def test_robots_disallowed_page_is_skipped_with_an_info_line(
    logs: list[dict], retries: list[dict], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def disallow(_client: httpx.AsyncClient, _url: str) -> bool:
        return False

    monkeypatch.setattr(crawler_service, "_robots_allows", disallow)

    crawler_tasks.crawl_url("https://a.test/private", "t", 1)

    assert [r["message"] for r in logs if r["level"].name == "INFO"] == [
        "skipped: disallowed by robots.txt (https://a.test/private)"
    ]
    assert retries == []
    assert warnings(logs) == []


def test_requeue_args_carry_the_collection_id(
    retries: list[dict], serve, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(httpx.Response(200, content=b"<p>hi</p>", headers=HTML))
    deny_rate_limit(monkeypatch)

    with pytest.raises(Retry):
        crawler_tasks.crawl_url("https://a.test/p", "t", 42)

    assert retries[0]["collection_id"] == 42


def stub_store(monkeypatch: pytest.MonkeyPatch, result: ingest.StoreResult) -> None:
    async def store(_db, _collection_id, _doc) -> ingest.StoreResult:
        return result

    monkeypatch.setattr(ingest, "store_extracted", store)


def infos(logs: list[dict]) -> list[str]:
    return [r["message"] for r in logs if r["level"].name == "INFO"]


def test_stored_page_logs_the_document_id(
    logs: list[dict], serve, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(httpx.Response(200, content=b"<p>hi</p>", headers=HTML))
    stub_store(monkeypatch, ingest.StoreResult(ingest.StoreOutcome.STORED, 7, chunks=3, tokens=250))

    crawler_tasks.crawl_url("https://a.test/p", "t", 1)

    assert "stored document 7 chunks=3 tokens=250" in infos(logs)


def test_duplicate_page_logs_the_existing_document_id(
    logs: list[dict], serve, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(httpx.Response(200, content=b"<p>hi</p>", headers=HTML))
    stub_store(monkeypatch, ingest.StoreResult(ingest.StoreOutcome.DUPLICATE, 3, "pending"))

    crawler_tasks.crawl_url("https://a.test/p", "t", 1)

    assert "duplicate of document 3" in infos(logs)


def test_missing_collection_logs_a_warning_without_raising(
    logs: list[dict], serve, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(httpx.Response(200, content=b"<p>hi</p>", headers=HTML))
    stub_store(monkeypatch, ingest.StoreResult(ingest.StoreOutcome.COLLECTION_MISSING))

    crawler_tasks.crawl_url("https://a.test/p", "t", 99)

    assert warnings(logs) == ["collection 99 not found"]


@pytest.fixture(autouse=True)
def embeds(monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """No broker in tests: record embed_document enqueues instead of publishing them."""
    calls: list[tuple] = []
    monkeypatch.setattr(
        crawler_tasks.embedding_tasks.embed_document,
        "delay",
        lambda *args: calls.append(args),
    )
    return calls


def test_stored_page_enqueues_embedding_once(
    embeds: list[tuple], serve, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(httpx.Response(200, content=b"<p>hi</p>", headers=HTML))
    stub_store(monkeypatch, ingest.StoreResult(ingest.StoreOutcome.STORED, 7))

    crawler_tasks.crawl_url("https://a.test/p", "t", 1)

    assert embeds == [(7, "t")]


def test_pending_duplicate_enqueues_embedding_again(
    embeds: list[tuple], serve, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(httpx.Response(200, content=b"<p>hi</p>", headers=HTML))
    stub_store(monkeypatch, ingest.StoreResult(ingest.StoreOutcome.DUPLICATE, 3, "pending"))

    crawler_tasks.crawl_url("https://a.test/p", "t", 1)

    assert embeds == [(3, "t")]


@pytest.mark.parametrize(
    "result",
    [
        ingest.StoreResult(ingest.StoreOutcome.DUPLICATE, 3, "ready"),
        ingest.StoreResult(ingest.StoreOutcome.COLLECTION_MISSING),
    ],
)
def test_ready_duplicate_and_missing_collection_do_not_enqueue(
    embeds: list[tuple], serve, monkeypatch: pytest.MonkeyPatch, result: ingest.StoreResult
) -> None:
    serve(httpx.Response(200, content=b"<p>hi</p>", headers=HTML))
    stub_store(monkeypatch, result)

    crawler_tasks.crawl_url("https://a.test/p", "t", 1)

    assert embeds == []
