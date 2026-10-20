import httpx
import pytest

from app.core.config import settings
from app.services import crawler as crawler_service
from app.services.crawler import CrawlOutcome, RateLimited

REAL_CLIENT = httpx.AsyncClient
PAGE = httpx.Response(200, content=b"<p>hi</p>", headers={"content-type": "text/html"})
ROBOTS_BLOCK_PRIVATE = "User-agent: *\nDisallow: /private/\n"


class Site:
    """A fake host: records every request path and the hosts the limiter was asked about."""

    def __init__(self, robots: httpx.Response) -> None:
        self.robots = robots
        self.paths: list[str] = []
        self.limited_hosts: list[str] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.paths.append(request.url.path)
        return self.robots if request.url.path == "/robots.txt" else PAGE


def robots_text(text: str) -> httpx.Response:
    return httpx.Response(200, text=text)


@pytest.fixture(autouse=True)
def clean_cache() -> None:
    crawler_service._robots_cache.clear()
    yield
    crawler_service._robots_cache.clear()


def serve(monkeypatch: pytest.MonkeyPatch, robots: httpx.Response, *, allow_limit=True) -> Site:
    site = Site(robots)
    transport = httpx.MockTransport(site.handle)
    monkeypatch.setattr(
        crawler_service.httpx, "AsyncClient", lambda: REAL_CLIENT(transport=transport)
    )

    async def acquire(host: str) -> bool:
        site.limited_hosts.append(host)
        return allow_limit

    monkeypatch.setattr(crawler_service, "_acquire", acquire)
    return site


async def test_allowed_path_is_fetched_after_robots_txt(monkeypatch: pytest.MonkeyPatch) -> None:
    site = serve(monkeypatch, robots_text(ROBOTS_BLOCK_PRIVATE))

    outcome, doc = await crawler_service.crawl_page("https://a.test/public")

    assert outcome is CrawlOutcome.EXTRACTED
    assert doc is not None
    assert site.paths == ["/robots.txt", "/public"]


async def test_disallowed_path_is_skipped_and_the_page_is_never_fetched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = serve(monkeypatch, robots_text(ROBOTS_BLOCK_PRIVATE))

    outcome, doc = await crawler_service.crawl_page("https://a.test/private/x")

    assert outcome is CrawlOutcome.ROBOTS_DISALLOWED
    assert doc is None
    assert site.paths == ["/robots.txt"]


async def test_missing_robots_txt_allows_everything(monkeypatch: pytest.MonkeyPatch) -> None:
    site = serve(monkeypatch, httpx.Response(404))

    outcome, _ = await crawler_service.crawl_page("https://a.test/private/x")

    assert outcome is CrawlOutcome.EXTRACTED
    assert site.paths == ["/robots.txt", "/private/x"]


async def test_robots_txt_server_error_disallows_everything(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = serve(monkeypatch, httpx.Response(503))

    outcome, doc = await crawler_service.crawl_page("https://a.test/public")

    assert (outcome, doc) == (CrawlOutcome.ROBOTS_DISALLOWED, None)
    assert site.paths == ["/robots.txt"]


async def test_unreachable_robots_txt_disallows_everything(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(monkeypatch, httpx.Response(200))

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    transport = httpx.MockTransport(refuse)
    monkeypatch.setattr(
        crawler_service.httpx, "AsyncClient", lambda: REAL_CLIENT(transport=transport)
    )

    outcome, _ = await crawler_service.crawl_page("https://a.test/public")

    assert outcome is CrawlOutcome.ROBOTS_DISALLOWED


async def test_robots_txt_is_fetched_once_per_host(monkeypatch: pytest.MonkeyPatch) -> None:
    site = serve(monkeypatch, robots_text(ROBOTS_BLOCK_PRIVATE))

    await crawler_service.crawl_page("https://a.test/one")
    await crawler_service.crawl_page("https://a.test/two")

    assert site.paths == ["/robots.txt", "/one", "/two"]


async def test_robots_txt_is_fetched_again_after_the_cache_expires(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = serve(monkeypatch, robots_text(ROBOTS_BLOCK_PRIVATE))
    monkeypatch.setattr(settings, "crawler_robots_cache_seconds", 0)

    await crawler_service.crawl_page("https://a.test/one")
    await crawler_service.crawl_page("https://a.test/two")

    assert site.paths.count("/robots.txt") == 2


async def test_the_rate_limit_is_requested_for_robots_txt_and_for_the_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = serve(monkeypatch, robots_text(ROBOTS_BLOCK_PRIVATE))

    await crawler_service.crawl_page("https://A.test/public")

    assert site.limited_hosts == ["a.test", "a.test"]


async def test_a_refused_slot_raises_rate_limited_before_any_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = serve(monkeypatch, robots_text(ROBOTS_BLOCK_PRIVATE), allow_limit=False)

    with pytest.raises(RateLimited):
        await crawler_service.crawl_page("https://a.test/public")

    assert site.paths == []
