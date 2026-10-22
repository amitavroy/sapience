from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import Chunk
from app.models.document import Document


async def get(db: AsyncSession, document_id: int) -> Document | None:
    return await db.get(Document, document_id)


async def list_chunks(db: AsyncSession, document_id: int) -> list[Chunk]:
    """A document's chunks in reading order."""
    result = await db.scalars(
        select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.chunk_index)
    )
    return list(result.all())
