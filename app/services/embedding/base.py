from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EmbedResult:
    vectors: list[list[float]]  # same order as the input texts
    tokens: int | None  # billed input tokens reported by the provider, if any
    cost: float | None  # USD, when the provider reports it (OpenRouter does)


class EmbeddingError(Exception):
    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class Embedder(Protocol):
    name: str  # "openrouter:openai/text-embedding-3-small", stored in document meta
    dimensions: int

    async def embed(self, texts: list[str]) -> EmbedResult: ...
