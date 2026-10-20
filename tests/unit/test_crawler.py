from pathlib import Path

import httpx
import pytest

from app.core.logger import logger
from app.tasks import crawler as crawler_tasks

PAGES = Path(__file__).parent.parent / "fixtures" / "pages"
REAL_CLIENT = httpx.AsyncClient


@pytest.fixture
def logs() -> list[dict]:
    """Records of everything logged at DEBUG and above during the test."""
    records: list[dict] = []
    sink = logger.add(lambda m: records.append(m.record), level="DEBUG")
    yield records
    logger.remove(sink)


@pytest.fixture
def serve(monkeypatch: pytest.MonkeyPatch):
    """Make the task's HTTP client answer every request with the given response."""

    def _serve(response: httpx.Response) -> None:
        transport = httpx.MockTransport(lambda _: response)
        monkeypatch.setattr(
            crawler_tasks.httpx, "AsyncClient", lambda: REAL_CLIENT(transport=transport)
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
