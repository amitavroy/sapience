import openai

from app.services.embedding.base import EmbeddingError, EmbedResult

# OpenRouter's documented status codes, a superset of OpenAI's
_RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504, 524, 529}


class OpenAICompatibleEmbedder:
    """Any OpenAI-compatible embeddings API: OpenRouter (default) or OpenAI itself."""

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        dimensions: int,
        api_key: str,
        base_url: str | None,
        timeout: float,
        http_client=None,
    ) -> None:
        self.name = f"{provider}:{model}"
        self.dimensions = dimensions
        self._model = model
        self._api_key = api_key
        # retrying is the task's job, so retries don't multiply
        self._client = openai.AsyncOpenAI(
            api_key=api_key or "unset",
            base_url=base_url,
            timeout=timeout,
            max_retries=0,
            http_client=http_client,
        )

    async def embed(self, texts: list[str]) -> EmbedResult:
        if not self._api_key:
            raise EmbeddingError("EMBEDDING_API_KEY is not set")
        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=texts,
                dimensions=self.dimensions,
                encoding_format="float",
            )
        except openai.APIStatusError as exc:
            raise _status_error(exc) from exc
        except (openai.APITimeoutError, openai.APIConnectionError) as exc:
            raise EmbeddingError(f"embedding request failed: {exc}", retryable=True) from exc

        # routers occasionally return incomplete payloads
        if len(response.data) != len(texts):
            raise EmbeddingError(
                f"expected {len(texts)} vectors, got {len(response.data)}", retryable=True
            )
        items = sorted(response.data, key=lambda item: item.index)
        if [item.index for item in items] != list(range(len(texts))):
            raise EmbeddingError(
                "embedding response indexes don't match the inputs", retryable=True
            )
        vectors = [item.embedding for item in items]
        for vector in vectors:
            if len(vector) != self.dimensions:
                raise EmbeddingError(
                    f"model {self._model} returned {len(vector)} dimensions, "
                    f"expected {self.dimensions}"
                )

        usage = response.usage
        cost = (getattr(usage, "model_extra", None) or {}).get("cost") if usage else None
        return EmbedResult(
            vectors=vectors,
            tokens=usage.total_tokens if usage else None,
            cost=float(cost) if cost is not None else None,
        )


def _status_error(exc: openai.APIStatusError) -> EmbeddingError:
    status = exc.status_code
    message = f"embedding API returned {status}: {exc.message}"
    if status == 402:
        message += " (out of credits: add credits at openrouter.ai/credits)"
    elif status == 413:
        message += " (request too large: lower embedding_batch_size)"
    return EmbeddingError(message, retryable=status in _RETRYABLE_STATUSES)
