"""add users.google_chat_user_id, nullable password_hash

Revision ID: c7d3e9f15a62
Revises: b4c81d5e7a20
Create Date: 2026-10-25 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7d3e9f15a62"
down_revision: str | Sequence[str] | None = "b4c81d5e7a20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("google_chat_user_id", sa.String(length=255), nullable=True))
    op.create_index(
        op.f("ix_users_google_chat_user_id"), "users", ["google_chat_user_id"], unique=True
    )
    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # users created from Chat have no password and cannot be kept under NOT NULL
    op.execute("DELETE FROM users WHERE password_hash IS NULL")
    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=False)
    op.drop_index(op.f("ix_users_google_chat_user_id"), table_name="users")
    op.drop_column("users", "google_chat_user_id")
