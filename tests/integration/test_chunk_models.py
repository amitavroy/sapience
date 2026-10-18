import pytest
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.types import EMBEDDING_DIM
from app.models import Chunk, Collection, Document

# SQLite stores embeddings as JSON, so these tests cover storage only, not vector search


async def make_document(
    session: AsyncSession, collection: Collection | None = None, content_hash: str = "a" * 64
) -> Document:
    if collection is None:
        collection = Collection(name="Handbook")
        session.add(collection)
        await session.flush()
    document = Document(collection_id=collection.id, title="intro.pdf", content_hash=content_hash)
    session.add(document)
    await session.flush()
    return document


def make_chunk(document: Document, index: int, **kwargs) -> Chunk:
    return Chunk(
        document_id=document.id,
        collection_id=document.collection_id,
        chunk_index=index,
        content=f"chunk {index}",
        token_count=2,
        **kwargs,
    )


async def test_create_chunks_with_embeddings(db_session: AsyncSession):
    document = await make_document(db_session)
    embedding = [0.5] * EMBEDDING_DIM
    db_session.add_all(
        [
            make_chunk(document, 0, embedding=embedding, meta={"page": 1}),
            make_chunk(document, 1),  # not embedded yet
        ]
    )
    await db_session.flush()
    db_session.expire_all()

    chunks = (await db_session.scalars(select(Chunk).order_by(Chunk.chunk_index))).all()
    assert [c.chunk_index for c in chunks] == [0, 1]
    assert list(chunks[0].embedding) == embedding
    assert chunks[0].meta == {"page": 1}
    assert chunks[1].embedding is None
    assert chunks[1].meta == {}


async def test_duplicate_chunk_index_rejected(db_session: AsyncSession):
    document = await make_document(db_session)
    db_session.add(make_chunk(document, 0))
    await db_session.flush()

    with pytest.raises(IntegrityError):
        await db_session.execute(
            insert(Chunk).values(
                document_id=document.id,
                collection_id=document.collection_id,
                chunk_index=0,
                content="dup",
                token_count=1,
            )
        )


async def test_same_chunk_index_in_another_document_allowed(db_session: AsyncSession):
    first = await make_document(db_session)
    collection = await db_session.get(Collection, first.collection_id)
    second = await make_document(db_session, collection, content_hash="b" * 64)
    db_session.add_all([make_chunk(first, 0), make_chunk(second, 0)])
    await db_session.flush()

    assert len((await db_session.scalars(select(Chunk.id))).all()) == 2


async def test_deleting_document_deletes_its_chunks(db_session: AsyncSession):
    first = await make_document(db_session)
    collection = await db_session.get(Collection, first.collection_id)
    second = await make_document(db_session, collection, content_hash="b" * 64)
    db_session.add_all([make_chunk(first, 0), make_chunk(first, 1), make_chunk(second, 0)])
    await db_session.flush()
    first_id, second_id = first.id, second.id

    await db_session.execute(delete(Document).where(Document.id == first_id))
    db_session.expire_all()

    remaining = await db_session.scalars(select(Chunk.document_id))
    assert remaining.all() == [second_id]


async def test_deleting_collection_deletes_its_chunks(db_session: AsyncSession):
    document = await make_document(db_session)
    other = await make_document(db_session, content_hash="b" * 64)  # its own collection
    db_session.add_all([make_chunk(document, 0), make_chunk(other, 0)])
    await db_session.flush()
    collection_id, other_collection_id = document.collection_id, other.collection_id

    await db_session.execute(delete(Collection).where(Collection.id == collection_id))
    db_session.expire_all()

    remaining = await db_session.scalars(select(Chunk.collection_id))
    assert remaining.all() == [other_collection_id]
