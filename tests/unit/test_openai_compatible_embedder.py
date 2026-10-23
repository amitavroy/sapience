import json

import httpx
import pytest

from app.core.config import settings
from app.db.types import EMBEDDING_DIM
from app.services import embedding
from app.services.embedding import EmbeddingError
from app.services.embedding.openai_compatible import OpenAICompatibleEmbedder


def vector(value: float, size: int = EMBEDDING_DIM) -> list[float]:
    return [value] * size


def embedder_for(handler, *, api_key: str = "key") -> tuple[OpenAICompatibleEmbedder, list]:
    requests: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    embedder = OpenAICompatibleEmbedder(
        provider="openrouter",
        model="openai/text-embedding-3-small",
        dimensions=EMBEDDING_DIM,
        api_key=api_key,
        base_url="https://router.test/api/v1",
        timeout=5,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(record)),
    )
    return embedder, requests


def ok(items: list[tuple[int, list[float]]], usage: dict | None = None) -> httpx.Response:
    body = {
        "object": "list",
        "model": "openai/text-embedding-3-small",
        "data": [{"object": "embedding", "index": i, "embedding": v} for i, v in items],
        "usage": usage or {"prompt_tokens": 7, "total_tokens": 7},
    }
    return httpx.Response(200, json=body)


@pytest.mark.parametrize("status", [429, 500, 502, 503, 524, 529])
async def test_retryable_statuses(status: int) -> None:
    embedder, _ = embedder_for(lambda _: httpx.Response(status, json={"error": {"message": "x"}}))

    with pytest.raises(EmbeddingError) as exc_info:
        await embedder.embed(["a"])

    assert exc_info.value.retryable is True


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404, 413])
async def test_permanent_statuses(status: int) -> None:
    embedder, _ = embedder_for(lambda _: httpx.Response(status, json={"error": {"message": "x"}}))

    with pytest.raises(EmbeddingError) as exc_info:
        await embedder.embed(["a"])

    assert exc_info.value.retryable is False


async def test_402_message_mentions_credits_and_413_the_batch_size() -> None:
    embedder, _ = embedder_for(lambda _: httpx.Response(402, json={"error": {"message": "x"}}))
    with pytest.raises(EmbeddingError, match="credits"):
        await embedder.embed(["a"])

    embedder, _ = embedder_for(lambda _: httpx.Response(413, json={"error": {"message": "x"}}))
    with pytest.raises(EmbeddingError, match="embedding_batch_size"):
        await embedder.embed(["a"])


async def test_timeout_is_retryable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    embedder, _ = embedder_for(handler)

    with pytest.raises(EmbeddingError) as exc_info:
        await embedder.embed(["a"])

    assert exc_info.value.retryable is True


async def test_empty_api_key_is_permanent_and_sends_nothing() -> None:
    embedder, requests = embedder_for(lambda _: ok([(0, vector(1))]), api_key="")

    with pytest.raises(EmbeddingError) as exc_info:
        await embedder.embed(["a"])

    assert exc_info.value.retryable is False
    assert requests == []


async def test_vectors_come_back_in_input_order_when_the_response_is_shuffled() -> None:
    embedder, _ = embedder_for(lambda _: ok([(2, vector(3)), (0, vector(1)), (1, vector(2))]))

    result = await embedder.embed(["a", "b", "c"])

    assert [v[0] for v in result.vectors] == [1, 2, 3]


async def test_too_few_vectors_is_retryable() -> None:
    embedder, _ = embedder_for(lambda _: ok([(0, vector(1))]))

    with pytest.raises(EmbeddingError) as exc_info:
        await embedder.embed(["a", "b"])

    assert exc_info.value.retryable is True


async def test_wrong_vector_length_is_permanent() -> None:
    embedder, _ = embedder_for(lambda _: ok([(0, vector(1, size=3))]))

    with pytest.raises(EmbeddingError, match="3 dimensions") as exc_info:
        await embedder.embed(["a"])

    assert exc_info.value.retryable is False


async def test_request_carries_model_dimensions_and_goes_to_the_base_url() -> None:
    embedder, requests = embedder_for(lambda _: ok([(0, vector(1))]))

    await embedder.embed(["hello"])

    assert str(requests[0].url) == "https://router.test/api/v1/embeddings"
    body = json.loads(requests[0].content)
    assert body["model"] == "openai/text-embedding-3-small"
    assert body["dimensions"] == EMBEDDING_DIM
    assert body["input"] == ["hello"]


async def test_tokens_and_cost_come_from_usage() -> None:
    usage = {"prompt_tokens": 9, "total_tokens": 9, "cost": 0.000018}
    embedder, _ = embedder_for(lambda _: ok([(0, vector(1))], usage))

    result = await embedder.embed(["a"])

    assert result.tokens == 9
    assert result.cost == pytest.approx(0.000018)


async def test_cost_is_none_for_an_openai_shaped_response() -> None:
    embedder, _ = embedder_for(lambda _: ok([(0, vector(1))]))

    result = await embedder.embed(["a"])

    assert result.tokens == 7
    assert result.cost is None


def test_openrouter_with_an_empty_base_url_uses_the_openrouter_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "openrouter")
    monkeypatch.setattr(settings, "embedding_base_url", "")

    embedder = embedding.get_embedder()

    assert str(embedder._client.base_url) == "https://openrouter.ai/api/v1/"


def test_an_explicit_base_url_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "openrouter")
    monkeypatch.setattr(settings, "embedding_base_url", "https://proxy.test/v1")

    embedder = embedding.get_embedder()

    assert str(embedder._client.base_url) == "https://proxy.test/v1/"
