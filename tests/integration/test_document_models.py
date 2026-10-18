import hashlib

import pytest
from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Collection, Document, DocumentStatus

HASH = hashlib.sha256(b"hello").hexdigest()


async def make_collection(session: AsyncSession, name: str = "Handbook") -> Collection:
    collection = Collection(name=name)
    session.add(collection)
    await session.flush()
    return collection


def make_document(collection: Collection, content_hash: str = HASH, **kwargs) -> Document:
    return Document(
        collection_id=collection.id, title="intro.pdf", content_hash=content_hash, **kwargs
    )


async def test_create_document_defaults(db_session: AsyncSession):
    collection = await make_collection(db_session)
    document = make_document(collection, source_uri="uploads/intro.pdf")
    db_session.add(document)
    await db_session.flush()
    await db_session.refresh(document)

    assert document.status == DocumentStatus.PENDING
    assert document.meta == {}
    assert document.error is None
    assert document.created_at is not None


async def test_meta_round_trips(db_session: AsyncSession):
    collection = await make_collection(db_session)
    document = make_document(collection, meta={"pages": 12, "tags": ["hr"]})
    db_session.add(document)
    await db_session.flush()
    await db_session.refresh(document)

    assert document.meta == {"pages": 12, "tags": ["hr"]}


async def test_duplicate_hash_in_same_collection_rejected(db_session: AsyncSession):
    collection = await make_collection(db_session)
    db_session.add(make_document(collection))
    await db_session.flush()

    with pytest.raises(IntegrityError):
        await db_session.execute(
            insert(Document).values(collection_id=collection.id, title="copy", content_hash=HASH)
        )


async def test_same_hash_in_another_collection_allowed(db_session: AsyncSession):
    first = await make_collection(db_session, "Handbook")
    second = await make_collection(db_session, "Policies")
    db_session.add_all([make_document(first), make_document(second)])
    await db_session.flush()

    assert await db_session.scalar(select(func.count()).select_from(Document)) == 2


async def test_bad_status_rejected(db_session: AsyncSession):
    collection = await make_collection(db_session)
    db_session.add(make_document(collection, status="archived"))

    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_deleting_collection_deletes_documents(db_session: AsyncSession):
    collection = await make_collection(db_session)
    other = await make_collection(db_session, "Policies")
    db_session.add_all(
        [make_document(collection), make_document(collection, "b" * 64), make_document(other)]
    )
    await db_session.flush()
    collection_id, other_id = collection.id, other.id

    await db_session.execute(delete(Collection).where(Collection.id == collection_id))
    db_session.expire_all()

    remaining = await db_session.scalars(select(Document.collection_id))
    assert remaining.all() == [other_id]
