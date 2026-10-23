import math

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.db.types import EMBEDDING_DIM
from app.models import Chunk, Collection, Document, DocumentStatus
from app.services.embedding import (
    EmbeddingError,
    EmbedResult,
    embedding_input,
    mark_failed,
    run_embedding,
)


class FakeEmbedder:
    name = "fake:model"
    dimensions = EMBEDDING_DIM

    def __init__(self, *, tokens: int | None = 10, cost: float | None = 0.5) -> None:
        self.tokens = tokens
        self.cost = cost
        self.batches: list[list[str]] = []
        self.fail_on_call: tuple[int, EmbeddingError] | None = None

    async def embed(self, texts: list[str]) -> EmbedResult:
        if self.fail_on_call and len(self.batches) + 1 == self.fail_on_call[0]:
            raise self.fail_on_call[1]
        self.batches.append(texts)
        vectors = [[float(len(t))] * EMBEDDING_DIM for t in texts]
        return EmbedResult(vectors=vectors, tokens=self.tokens, cost=self.cost)


async def make_document(db: AsyncSession, chunks: int = 5, **kwargs) -> Document:
    collection = Collection(name="Docs")
    db.add(collection)
    await db.flush()
    document = Document(
        collection_id=collection.id,
        title="A page",
        content_hash="hash",
        status=kwargs.pop("status", DocumentStatus.PENDING),
        **kwargs,
    )
    document.chunks = [
        Chunk(
            collection_id=collection.id,
            chunk_index=i,
            content=f"chunk {i}",
            token_count=2,
            meta={"heading_path": ["Guide", "Install"]},
        )
        for i in range(chunks)
    ]
    db.add(document)
    await db.commit()
    return document


async def chunks_of(db: AsyncSession, document: Document) -> list[Chunk]:
    return list(
        await db.scalars(
            select(Chunk).where(Chunk.document_id == document.id).order_by(Chunk.chunk_index)
        )
    )


async def test_fills_every_embedding_and_marks_the_document_ready(db_session: AsyncSession) -> None:
    document = await make_document(db_session, chunks=3)

    await run_embedding(db_session, document.id, FakeEmbedder(), batch_size=10)

    await db_session.refresh(document)
    assert document.status == DocumentStatus.READY
    assert document.error is None
    assert all(c.embedding is not None for c in await chunks_of(db_session, document))
    assert document.meta["embedding"] == {
        "model": "fake:model",
        "dimensions": EMBEDDING_DIM,
        "tokens": 10,
        "cost": 0.5,
    }


async def test_batches_by_size_with_the_breadcrumb_inputs(db_session: AsyncSession) -> None:
    document = await make_document(db_session, chunks=5)
    embedder = FakeEmbedder()

    await run_embedding(db_session, document.id, embedder, batch_size=2)

    assert [len(b) for b in embedder.batches] == [2, 2, 1]
    assert len(embedder.batches) == math.ceil(5 / 2)
    assert embedder.batches[0][0] == "A page\nGuide > Install\n\nchunk 0"
    await db_session.refresh(document)
    assert document.meta["embedding"]["tokens"] == 30  # summed over the three batches
    assert document.meta["embedding"]["cost"] == pytest.approx(1.5)


async def test_resume_skips_embedded_chunks_and_keeps_the_earlier_totals(
    db_session: AsyncSession,
) -> None:
    document = await make_document(db_session, chunks=4)
    first = FakeEmbedder()
    first.fail_on_call = (2, EmbeddingError("rate limited", retryable=True))

    with pytest.raises(EmbeddingError):
        await run_embedding(db_session, document.id, first, batch_size=2)

    await db_session.refresh(document)
    assert document.status == DocumentStatus.PROCESSING
    assert document.meta["embedding"]["tokens"] == 10

    second = FakeEmbedder()
    await run_embedding(db_session, document.id, second, batch_size=2)

    assert [b[0].rsplit("\n", 1)[-1] for b in second.batches] == ["chunk 2"]
    await db_session.refresh(document)
    assert document.status == DocumentStatus.READY
    assert document.meta["embedding"]["tokens"] == 20
    assert document.meta["embedding"]["cost"] == pytest.approx(1.0)


async def test_retryable_error_propagates_and_leaves_the_document_processing(
    db_session: AsyncSession,
) -> None:
    document = await make_document(db_session, chunks=2)
    embedder = FakeEmbedder()
    embedder.fail_on_call = (1, EmbeddingError("boom", retryable=True))

    with pytest.raises(EmbeddingError) as exc_info:
        await run_embedding(db_session, document.id, embedder)

    assert exc_info.value.retryable is True
    await db_session.refresh(document)
    assert document.status == DocumentStatus.PROCESSING


async def test_permanent_error_propagates_not_retryable(db_session: AsyncSession) -> None:
    document = await make_document(db_session, chunks=2)
    embedder = FakeEmbedder()
    embedder.fail_on_call = (1, EmbeddingError("bad key"))

    with pytest.raises(EmbeddingError) as exc_info:
        await run_embedding(db_session, document.id, embedder)

    assert exc_info.value.retryable is False


async def test_tokens_and_cost_are_left_out_when_not_reported(db_session: AsyncSession) -> None:
    document = await make_document(db_session, chunks=2)

    await run_embedding(db_session, document.id, FakeEmbedder(tokens=None, cost=None))

    await db_session.refresh(document)
    assert document.meta["embedding"] == {"model": "fake:model", "dimensions": EMBEDDING_DIM}


async def test_a_ready_document_makes_no_embedder_call(db_session: AsyncSession) -> None:
    document = await make_document(db_session, status=DocumentStatus.READY)
    embedder = FakeEmbedder()

    await run_embedding(db_session, document.id, embedder)

    assert embedder.batches == []


async def test_a_missing_document_logs_a_warning(db_session: AsyncSession) -> None:
    records: list[dict] = []
    sink = logger.add(lambda m: records.append(m.record), level="WARNING")
    embedder = FakeEmbedder()

    await run_embedding(db_session, 999, embedder)

    logger.remove(sink)
    assert embedder.batches == []
    assert [r["message"] for r in records] == ["document 999 not found, nothing to embed"]


async def test_embedding_input_has_title_and_path_and_drops_an_empty_path() -> None:
    with_path = Chunk(content="Body", meta={"heading_path": ["A", "B"]})
    without_path = Chunk(content="Body", meta={"heading_path": []})

    assert embedding_input("Title", with_path) == "Title\nA > B\n\nBody"
    assert embedding_input("Title", without_path) == "Title\n\nBody"


async def test_mark_failed_sets_status_and_error(db_session: AsyncSession) -> None:
    document = await make_document(db_session, chunks=1)

    await mark_failed(db_session, document.id, "provider down")

    await db_session.refresh(document)
    assert document.status == DocumentStatus.FAILED
    assert document.error == "provider down"


async def test_mark_failed_ignores_missing_document(db_session: AsyncSession) -> None:
    await mark_failed(db_session, 999, "provider down")  # must not raise
