"""enable vector extension

Revision ID: 85c18b7736cd
Revises: 47ac13195b65
Create Date: 2026-10-18 11:47:41.109071

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "85c18b7736cd"
down_revision: str | Sequence[str] | None = "47ac13195b65"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Postgres may run outside Docker: the pgvector binaries must be installed on the server
    # and the migration role must be allowed to create extensions.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    """Downgrade schema."""
    # Leave the extension in place: other databases/schemas on the server may use it.
    pass
