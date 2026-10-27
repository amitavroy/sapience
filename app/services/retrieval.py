from typing import Protocol, TypedDict, runtime_checkable

from sqlalchemy import Select, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import Chunk
from app.models.collection import CollectionMember
from app.models.document import Document
from app.models.user import User

PROBE_K = 5  # nearest chunks per rewritten query
DEEP_K = 8  # chunks the agent answers from


class RetrievedChunk(TypedDict):
    chunk_id: int
    document_id: int
    title: str
    source_uri: str | None
    content: str
    distance: float


@runtime_checkable  # LangGraph validates the runtime context, and pydantic needs isinstance
class KnowledgeSearch(Protocol):
    """What the graph and the search tool see; the task layer owns embedding and sessions."""

    async def probe(self, user_id: int, queries: list[str]) -> list[RetrievedChunk]: ...

    async def deep_search(
        self, user_id: int, query: str, doc_ids: list[int] | None
    ) -> list[RetrievedChunk]: ...


def _member_collections(user_id: int) -> Select:
    # inactive users match nothing, so a user deactivated after queueing finds no chunks
    return (
        select(CollectionMember.collection_id)
        .join(User, User.id == CollectionMember.user_id)
        .where(User.id == user_id, User.is_active)
    )


def _nearest(user_id: int, vector: list[float], k: int) -> Select:
    distance = Chunk.embedding.cosine_distance(vector)
    return (
        select(
            Chunk.id.label("chunk_id"),
            Chunk.document_id,
            Document.title,
            Document.source_uri,
            Chunk.content,
            distance.label("distance"),
        )
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.collection_id.in_(_member_collections(user_id)), Chunk.embedding.is_not(None))
        .order_by(distance)
        .limit(k)
    )


def _dedup(rows) -> list[RetrievedChunk]:
    """One entry per chunk (the closest match across queries), nearest first."""
    best: dict[int, RetrievedChunk] = {}
    for row in rows:
        chunk = RetrievedChunk(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            title=row.title,
            source_uri=row.source_uri,
            content=row.content,
            distance=float(row.distance),
        )
        if chunk["chunk_id"] not in best or chunk["distance"] < best[chunk["chunk_id"]]["distance"]:
            best[chunk["chunk_id"]] = chunk
    return sorted(best.values(), key=lambda c: c["distance"])


def probe_statement(user_id: int, vectors: list[list[float]], k: int = PROBE_K):
    # each branch keeps its own order by + limit, so each one scans the HNSW index; SQLAlchemy
    # parenthesises a limited select inside a UNION ALL
    return union_all(*(_nearest(user_id, v, k) for v in vectors))


async def probe(
    db: AsyncSession, user_id: int, vectors: list[list[float]], k: int = PROBE_K
) -> list[RetrievedChunk]:
    """Every query's nearest chunks in one round trip."""
    if not vectors:
        return []
    return _dedup((await db.execute(probe_statement(user_id, vectors, k))).all())


async def deep_search(
    db: AsyncSession,
    user_id: int,
    vector: list[float],
    doc_ids: list[int] | None,
    k: int = DEEP_K,
) -> list[RetrievedChunk]:
    """Nearest chunks, optionally within some documents; always within the user's collections.

    The membership filter applies even with doc ids, so an id from a stale checkpoint can never
    reach a collection the user has since left.
    """
    stmt = _nearest(user_id, vector, k)
    if doc_ids is not None:
        stmt = stmt.where(Chunk.document_id.in_(doc_ids))
    return _dedup((await db.execute(stmt)).all())
