import pytest
from typer.testing import CliRunner

from app.cli import __main__ as cli


@pytest.fixture
def queued(monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    calls: list[tuple] = []
    monkeypatch.setattr(cli.crawler_tasks.crawl_url, "delay", lambda *args: calls.append(args))
    return calls


def test_crawl_url_enqueues_one_task_with_the_trace_id(queued: list[tuple]) -> None:
    result = CliRunner().invoke(cli.app, ["crawl-url", "https://example.com/page"])

    assert result.exit_code == 0
    [(url, trace)] = queued
    assert url == "https://example.com/page"
    assert trace
    assert f"queued: https://example.com/page (trace {trace})" in result.output


@pytest.mark.parametrize("url", ["ftp://example.com/file", "not-a-url"])
def test_crawl_url_rejects_non_http_urls(queued: list[tuple], url: str) -> None:
    result = CliRunner().invoke(cli.app, ["crawl-url", url])

    assert result.exit_code == 1
    assert queued == []
