import httpx
import pytest
from limits import parse
from limits.aio.storage import MemoryStorage
from limits.aio.strategies import FixedWindowRateLimiter

from app.core import limiter
from app.main import app


async def test_requests_over_limit_get_429(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(limiter, "strategy", FixedWindowRateLimiter(MemoryStorage()))
    monkeypatch.setattr(limiter, "rate", parse("2/minute"))
    app.dependency_overrides.pop(limiter.rate_limit)

    codes = [(await client.get("/health")).status_code for _ in range(3)]

    assert codes == [200, 200, 429]


async def test_limiter_backend_down_returns_503(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BrokenStrategy:
        async def hit(self, *_: object) -> bool:
            raise RuntimeError("redis down")

    monkeypatch.setattr(limiter, "strategy", BrokenStrategy())
    app.dependency_overrides.pop(limiter.rate_limit)

    response = await client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "Rate limiter unavailable"}


async def test_lifespan_enters_redis_client(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []

    class FakeRedis:
        async def __aenter__(self) -> None:
            events.append("enter")

        async def __aexit__(self, *_: object) -> None:
            events.append("exit")

    monkeypatch.setattr(limiter, "redis", FakeRedis())

    async with app.router.lifespan_context(app):
        assert events == ["enter"]

    assert events == ["enter", "exit"]
