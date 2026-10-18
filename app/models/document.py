from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import JSONType

if TYPE_CHECKING:
    from app.models.chunk import Chunk
    from app.models.collection import Collection


class DocumentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        # same file can live in two collections, but only once per collection
        UniqueConstraint("collection_id", "content_hash", name="uq_documents_collection_hash"),
        CheckConstraint(
            "status IN ({})".format(", ".join(f"'{s.value}'" for s in DocumentStatus)),
            name="ck_documents_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    collection_id: Mapped[int] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), index=True
    )
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(500))
    source_uri: Mapped[str | None] = mapped_column(String(1000))
    mime_type: Mapped[str | None] = mapped_column(String(100))
    content_hash: Mapped[str] = mapped_column(String(64))  # sha256 hex of the raw content
    status: Mapped[str] = mapped_column(
        String(20), default=DocumentStatus.PENDING, server_default=DocumentStatus.PENDING.value
    )
    error: Mapped[str | None] = mapped_column(Text)
    # `metadata` is reserved on declarative classes, so the attribute is `meta`
    meta: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONType, default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    collection: Mapped["Collection"] = relationship(back_populates="documents")
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )
