from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import User

if TYPE_CHECKING:
    from app.models.document import Document


class CollectionRole(StrEnum):
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    # audit only; access is decided by `collection_members`
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    members: Mapped[list["CollectionMember"]] = relationship(
        back_populates="collection", cascade="all, delete-orphan", passive_deletes=True
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="collection", cascade="all, delete-orphan", passive_deletes=True
    )


class CollectionMember(Base):
    __tablename__ = "collection_members"
    __table_args__ = (
        CheckConstraint(
            "role IN ({})".format(", ".join(f"'{r.value}'" for r in CollectionRole)),
            name="ck_collection_members_role",
        ),
    )

    collection_id: Mapped[int] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    role: Mapped[str] = mapped_column(
        String(20), default=CollectionRole.VIEWER, server_default=CollectionRole.VIEWER.value
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    collection: Mapped[Collection] = relationship(back_populates="members")
    user: Mapped[User] = relationship()
