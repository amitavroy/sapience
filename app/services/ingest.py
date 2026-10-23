import asyncio
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus
from app.schemas.extracted_document import ExtractedDocument
from app.services import chunking
from app.services import collection as collection_service


class StoreOutcome(StrEnum):
    STORED = "stored"
    DUPLICATE = "duplicate"
    COLLECTION_MISSING = "collection_missing"


@dataclass(frozen=True)
class StoreResult:
    outcome: StoreOutcome
    document_id: int | None = None
    status: str | None = None  # of the existing document, for DUPLICATE
    chunks: int = 0
    tokens: int = 0


async def _find_by_hash(db: AsyncSession, collection_id: int, content_hash: str) -> Document | None:
    return await db.scalar(
        select(Document).where(
            Document.collection_id == collection_id, Document.content_hash == content_hash
        )
    )


def _duplicate(existing: Document) -> StoreResult:
    return StoreResult(StoreOutcome.DUPLICATE, existing.id, existing.status)


async def store_extracted(
    db: AsyncSession, collection_id: int, doc: ExtractedDocument
) -> StoreResult:
    """Insert a pending Document with its extracted content and chunks, in one transaction."""
    if not await collection_service.exists(db, collection_id):
        return StoreResult(StoreOutcome.COLLECTION_MISSING)
    if (existing := await _find_by_hash(db, collection_id, doc.content_hash)) is not None:
        return _duplicate(existing)

    chunker = chunking.chunker_for(doc.mime_type)
    # SYNC-EXCEPTION: chunking is CPU-bound; called via asyncio.to_thread inside the Celery worker
    drafts = await asyncio.to_thread(chunker.chunk, doc)

    document = Document(
        collection_id=collection_id,
        title=doc.title[:500],
        source_uri=doc.source_uri[:1000],
        mime_type=doc.mime_type,
        content_hash=doc.content_hash,
        status=DocumentStatus.PENDING,
        meta={
            **doc.metadata,
            "requested_url": doc.requested_url,
            "status_code": doc.status_code,
            "fetched_at": doc.fetched_at.isoformat() if doc.fetched_at else None,
            "chunker": chunker.name,
            "chunker_version": chunker.version,
        },
        content=doc.model_dump(mode="json", exclude_defaults=True),
    )
    document.chunks = [
        Chunk(
            collection_id=collection_id,
            chunk_index=index,
            content=draft.content,
            token_count=draft.token_count,
            meta={
                "heading_path": draft.heading_path,
                "blocks": [draft.block_start, draft.block_end],
                "chunker": chunker.name,
                "chunker_version": chunker.version,
            },
        )
        for index, draft in enumerate(drafts)
    ]
    db.add(document)
    try:
        await db.commit()
    except IntegrityError:  # a concurrent task stored the same page
        await db.rollback()
        existing = await _find_by_hash(db, collection_id, doc.content_hash)
        if existing is None:
            raise
        return _duplicate(existing)
    return StoreResult(
        StoreOutcome.STORED,
        document.id,
        chunks=len(drafts),
        tokens=sum(d.token_count for d in drafts),
    )
