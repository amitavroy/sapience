import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db
from app.core.logger import logger
from app.main import app

GOOD_ID = "abc12345-trace"


def client_from(ip: str) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app, client=(ip, 12345))
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture(autouse=True)
def _no_limiter(client: httpx.AsyncClient) -> None:
    """Reuse the `client` fixture's dependency overrides (limiter off, test DB)."""


async def get_id(ip: str, header: str | None = GOOD_ID) -> str:
    headers = {"X-Request-ID": header} if header is not None else {}
    async with client_from(ip) as c:
        response = await c.get("/health", headers=headers)
    return response.headers["X-Request-ID"]


async def test_generates_id_without_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "trusted_proxies", "10.0.0.1")

    tid = await get_id("10.0.0.1", header=None)

    assert len(tid) == 32


async def test_untrusted_peer_header_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "trusted_proxies", "10.0.0.1")

    assert await get_id("203.0.113.9") != GOOD_ID


async def test_empty_setting_trusts_nobody(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "trusted_proxies", "")

    assert await get_id("10.0.0.1") != GOOD_ID


async def test_trusted_peer_header_adopted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "trusted_proxies", "10.0.0.1")

    assert await get_id("10.0.0.1") == GOOD_ID


@pytest.mark.parametrize("bad", ["short", "x" * 65, "has space 12345", "bad;chars-123"])
async def test_invalid_header_from_trusted_peer_replaced(
    monkeypatch: pytest.MonkeyPatch, bad: str
) -> None:
    monkeypatch.setattr(settings, "trusted_proxies", "10.0.0.1")

    assert await get_id("10.0.0.1", header=bad) != bad


async def test_comma_separated_and_cidr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "trusted_proxies", " 192.168.1.5 , 10.1.0.0/16,")

    assert await get_id("192.168.1.5") == GOOD_ID
    assert await get_id("10.1.200.3") == GOOD_ID
    assert await get_id("10.2.0.1") != GOOD_ID


async def test_log_records_share_request_trace_id(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    def get_db_logging() -> AsyncSession:
        logger.info("inside request")
        return db_session

    app.dependency_overrides[get_db] = get_db_logging
    records: list[dict] = []
    sink = logger.add(lambda m: records.append(m.record), level="INFO")
    try:
        logger.info("outside request")
        response = await client.get("/health")
    finally:
        logger.remove(sink)

    tid = response.headers["X-Request-ID"]
    by_message = {r["message"].split(" ")[0]: r["extra"]["trace_id"] for r in records}
    assert by_message["outside"] == "-"
    assert by_message["inside"] == tid
    assert by_message["GET"] == tid  # the middleware's own request line
