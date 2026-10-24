from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Channel(StrEnum):
    GOOGLE_CHAT = "google_chat"
    WEB = "web"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class MessageStatus(StrEnum):
    PENDING = "pending"
    ANSWERED = "answered"
    FAILED = "failed"
    EXPIRED = "expired"


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("channel", "thread_id", name="uq_conversations_channel_thread"),
        CheckConstraint(
            "channel IN ({})".format(", ".join(f"'{c.value}'" for c in Channel)),
            name="ck_conversations_channel",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    channel: Mapped[str] = mapped_column(String(20))
    # the LangGraph thread id, e.g. `gchat:{space}:{user}`
    thread_id: Mapped[str] = mapped_column(String(500))
    space: Mapped[str | None] = mapped_column(String(255))
    # the Chat `users/…` id; null for channels without one
    external_user: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255), default="", server_default="")
    # for a future web login
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_message_at: Mapped[datetime] = mapped_column(server_default=func.now())

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", passive_deletes=True
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        # NULLs don't collide, so rows without an external id are unconstrained
        UniqueConstraint(
            "conversation_id", "external_id", name="uq_messages_conversation_external"
        ),
        CheckConstraint(
            "role IN ({})".format(", ".join(f"'{r.value}'" for r in MessageRole)),
            name="ck_messages_role",
        ),
        CheckConstraint(
            "status IS NULL OR status IN ({})".format(
                ", ".join(f"'{s.value}'" for s in MessageStatus)
            ),
            name="ck_messages_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # lookups by conversation use the unique constraint's leading column, so no separate index
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    # Chat message name on user rows, `{message_name}#reply` on assistant rows
    external_id: Mapped[str | None] = mapped_column(String(500))
    # name of the reply Chat posted; differs per rerun, so it is not in `external_id`
    chat_message_name: Mapped[str | None] = mapped_column(String(500))
    # user rows only
    status: Mapped[str | None] = mapped_column(String(20))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
