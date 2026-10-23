import math
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logger import logger
from app.db.types import EMBEDDING_DIM
from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus
from app.services.embedding.base import Embedder, EmbeddingError, EmbedResult
from app.services.embedding.openai_compatible import OpenAICompatibleEmbedder

__all__ = [
    "Embedder",
    "EmbedResult",
    "EmbeddingError",
    "embedding_input",
    "get_embedder",
    "mark_failed",
    "run_embedding",
]

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def get_embedder() -> Embedder:
    """By settings.embedding_provider: "openrouter" or "openai"."""
    default_url = _OPENROUTER_BASE_URL if settings.embedding_provider == "openrouter" else None
    embedder = OpenAICompatibleEmbedder(
        provider=settings.embedding_provider,
        model=settings.embedding_model,
        dimensions=EMBEDDING_DIM,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url or default_url,
        timeout=settings.embedding_timeout_seconds,
    )
    if embedder.dimensions != EMBEDDING_DIM:
        raise EmbeddingError(
            f"embedder gives {embedder.dimensions} dimensions, need {EMBEDDING_DIM}"
        )
    return embedder


def embedding_input(title: str | None, chunk: Chunk) -> str:
    """Title and heading breadcrumb plus content: the breadcrumb goes into the vector only."""
    heading_path = (chunk.meta or {}).get("heading_path") or []
    lines = [title or ""]
    if heading_path:
        lines.append(" > ".join(heading_path))
    return "\n".join(lines) + "\n\n" + chunk.content


async def mark_failed(db: AsyncSession, document_id: int, error: str) -> None:
    document = await db.get(Document, document_id)
    if document is not None:
        document.status = DocumentStatus.FAILED
        document.error = error
        await db.commit()


async def run_embedding(
    db: AsyncSession,
    document_id: int,
    embedder: Embedder,
    batch_size: int | None = None,
) -> None:
    """Embed a document's chunks that have no vector yet, committing after each batch.

    A retryable EmbeddingError propagates with the document left `processing`, so a retry
    resumes where this run stopped.
    """
    batch_size = batch_size or settings.embedding_batch_size
    started = time.monotonic()
    document = await db.get(Document, document_id)
    if document is None:
        logger.warning("document {} not found, nothing to embed", document_id)
        return
    if document.status == DocumentStatus.READY:
        return

    document.status = DocumentStatus.PROCESSING
    document.error = None
    await db.commit()

    chunks = list(
        await db.scalars(
            select(Chunk)
            .where(Chunk.document_id == document_id, Chunk.embedding.is_(None))
            .order_by(Chunk.chunk_index)
        )
    )
    # totals carry over from earlier runs, so a resumed document still covers every batch
    totals = dict((document.meta or {}).get("embedding") or {})
    tokens = totals.get("tokens", 0)
    cost = totals.get("cost", 0.0)
    reported_tokens = "tokens" in totals
    reported_cost = "cost" in totals
    batches = math.ceil(len(chunks) / batch_size)

    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        result = await embedder.embed([embedding_input(document.title, c) for c in batch])
        for chunk, vector in zip(batch, result.vectors, strict=True):
            chunk.embedding = vector
        if result.tokens is not None:
            tokens += result.tokens
            reported_tokens = True
        if result.cost is not None:
            cost += result.cost
            reported_cost = True
        document.meta = {
            **document.meta,
            "embedding": _embedding_meta(embedder, tokens, cost, reported_tokens, reported_cost),
        }
        await db.commit()

    document.status = DocumentStatus.READY
    document.meta = {
        **document.meta,
        "embedding": _embedding_meta(embedder, tokens, cost, reported_tokens, reported_cost),
    }
    await db.commit()
    logger.info(
        "embedded document {}: chunks={} batches={} tokens={} cost={} duration_ms={}",
        document_id,
        len(chunks),
        batches,
        tokens if reported_tokens else None,
        cost if reported_cost else None,
        round((time.monotonic() - started) * 1000),
    )


def _embedding_meta(
    embedder: Embedder, tokens: int, cost: float, reported_tokens: bool, reported_cost: bool
) -> dict:
    meta: dict = {"model": embedder.name, "dimensions": embedder.dimensions}
    if reported_tokens:
        meta["tokens"] = tokens
    if reported_cost:
        meta["cost"] = cost
    return meta
