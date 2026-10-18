from datetime import datetime
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import EMBEDDING_DIM, JSONType

if TYPE_CHECKING:
    from app.models.document import Document

# pgvector on Postgres; SQLite (tests) has no vector type, so store the floats as JSON there
EmbeddingType = Vector(EMBEDDING_DIM).with_variant(JSON(), "sqlite")


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunks_document_index"),
        # cosine distance suits OpenAI embeddings, which are normalized
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    # BIGINT on Postgres; SQLite only autoincrements a plain INTEGER primary key
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), primary_key=True
    )
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    # denormalized from the document so search can filter by collection without a join
    collection_id: Mapped[int] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int]  # position within the document
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int]
    # NULL until the embed step has run
    embedding: Mapped[list[float] | None] = mapped_column(EmbeddingType)
    meta: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONType, default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    document: Mapped["Document"] = relationship(back_populates="chunks")
