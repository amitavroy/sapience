from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk, Collection, Document, DocumentStatus
from app.schemas.extracted_document import ExtractedDocument
from app.services import chunking, ingest


def make_doc(content_hash: str = "hash-1", **kwargs) -> ExtractedDocument:
    fields = {
        "source_uri": "https://a.test/final",
        "title": "A page",
        "mime_type": "text/html",
        "content_hash": content_hash,
        "requested_url": "https://a.test/start",
        "status_code": 200,
        "fetched_at": datetime(2026, 10, 21, 9, 0, tzinfo=UTC),
        "metadata": {"language": "en"},
        "blocks": [{"type": "paragraph", "text": "Hello world"}],
    }
    return ExtractedDocument(**{**fields, **kwargs})


async def make_collection(db: AsyncSession, name: str = "Docs") -> Collection:
    collection = Collection(name=name)
    db.add(collection)
    await db.commit()
    return collection


async def count_documents(db: AsyncSession) -> int:
    return await db.scalar(select(func.count()).select_from(Document))


async def test_stores_a_pending_document_with_mapped_columns(db_session: AsyncSession) -> None:
    collection = await make_collection(db_session)
    doc = make_doc()

    result = await ingest.store_extracted(db_session, collection.id, doc)

    assert result.outcome is ingest.StoreOutcome.STORED
    document = await db_session.get(Document, result.document_id)
    assert document.status == DocumentStatus.PENDING
    assert document.collection_id == collection.id
    assert document.title == "A page"
    assert document.source_uri == "https://a.test/final"
    assert document.mime_type == "text/html"
    assert document.content_hash == "hash-1"
    assert document.meta["language"] == "en"
    assert document.meta["requested_url"] == "https://a.test/start"
    assert document.meta["status_code"] == 200
    assert document.meta["fetched_at"].startswith("2026-10-21T09:00")
    assert document.uploaded_by_id is None


async def test_content_round_trips_into_an_extracted_document(db_session: AsyncSession) -> None:
    collection = await make_collection(db_session)
    doc = make_doc()
    result = await ingest.store_extracted(db_session, collection.id, doc)

    # select the column itself: it is deferred, so lazy-loading it on the model fails in async
    content = await db_session.scalar(
        select(Document.content).where(Document.id == result.document_id)
    )

    assert ExtractedDocument.model_validate(content) == doc


async def test_long_title_and_source_uri_are_truncated(db_session: AsyncSession) -> None:
    collection = await make_collection(db_session)
    doc = make_doc(title="t" * 600, source_uri="https://a.test/" + "p" * 1100)

    result = await ingest.store_extracted(db_session, collection.id, doc)

    document = await db_session.get(Document, result.document_id)
    assert len(document.title) == 500
    assert len(document.source_uri) == 1000


async def test_same_hash_in_the_same_collection_is_a_duplicate(db_session: AsyncSession) -> None:
    collection = await make_collection(db_session)
    first = await ingest.store_extracted(db_session, collection.id, make_doc())

    second = await ingest.store_extracted(db_session, collection.id, make_doc())

    assert second.outcome is ingest.StoreOutcome.DUPLICATE
    assert second.document_id == first.document_id
    assert second.status == DocumentStatus.PENDING
    assert await count_documents(db_session) == 1


async def test_same_hash_in_another_collection_is_stored(db_session: AsyncSession) -> None:
    one = await make_collection(db_session, "One")
    two = await make_collection(db_session, "Two")
    await ingest.store_extracted(db_session, one.id, make_doc())

    result = await ingest.store_extracted(db_session, two.id, make_doc())

    assert result.outcome is ingest.StoreOutcome.STORED
    assert await count_documents(db_session) == 2


async def test_missing_collection_stores_nothing(db_session: AsyncSession) -> None:
    result = await ingest.store_extracted(db_session, 999, make_doc())

    assert result.outcome is ingest.StoreOutcome.COLLECTION_MISSING
    assert result.document_id is None
    assert await count_documents(db_session) == 0


async def stored_chunks(db: AsyncSession) -> list[Chunk]:
    return list((await db.scalars(select(Chunk).order_by(Chunk.chunk_index))).all())


def make_long_doc() -> ExtractedDocument:
    """Three sections of about 300 estimated tokens each, so the web chunker splits them."""
    paragraph = " ".join(["lorem"] * 200)
    blocks = []
    sections = []
    for name in ("One", "Two", "Three"):
        start = len(blocks)
        blocks += [
            {"type": "heading", "text": name, "level": 1},
            {"type": "paragraph", "text": f"{name} {paragraph}"},
        ]
        sections.append({"heading_path": [name], "start": start, "end": len(blocks)})
    return make_doc(blocks=blocks, sections=sections, content_hash="long")


async def test_stores_chunks_with_contiguous_index_and_no_embedding(
    db_session: AsyncSession,
) -> None:
    collection = await make_collection(db_session)

    result = await ingest.store_extracted(db_session, collection.id, make_long_doc())

    chunks = await stored_chunks(db_session)
    assert len(chunks) == result.chunks > 1
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert result.tokens == sum(c.token_count for c in chunks)
    for chunk in chunks:
        assert chunk.document_id == result.document_id
        assert chunk.collection_id == collection.id
        assert chunk.embedding is None
        assert chunk.token_count > 0
    assert [c.meta["heading_path"] for c in chunks] == [["One"], ["Two"], ["Three"]]
    assert chunks[0].meta["blocks"] == [0, 2]
    assert chunks[0].meta["chunker"] == "web"
    assert chunks[0].meta["chunker_version"] == 1


async def test_document_meta_records_the_chunker(db_session: AsyncSession) -> None:
    collection = await make_collection(db_session)

    result = await ingest.store_extracted(db_session, collection.id, make_doc())

    document = await db_session.get(Document, result.document_id)
    assert document.meta["chunker"] == "web"
    assert document.meta["chunker_version"] == 1


async def test_a_duplicate_stores_no_extra_chunks(db_session: AsyncSession) -> None:
    collection = await make_collection(db_session)
    first = await ingest.store_extracted(db_session, collection.id, make_long_doc())

    await ingest.store_extracted(db_session, collection.id, make_long_doc())

    assert len(await stored_chunks(db_session)) == first.chunks


async def test_a_mime_type_without_a_chunker_stores_nothing(db_session: AsyncSession) -> None:
    collection = await make_collection(db_session)

    with pytest.raises(chunking.NoChunkerError):
        await ingest.store_extracted(
            db_session, collection.id, make_doc(mime_type="application/pdf")
        )

    assert await count_documents(db_session) == 0
