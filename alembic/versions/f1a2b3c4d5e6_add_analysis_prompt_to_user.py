"""Add analysis prompt to user.

Revision ID: f1a2b3c4d5e6
Revises: e70c3b9a1d20
Create Date: 2026-09-08 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "e70c3b9a1d20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the optional custom analysis prompt."""
    op.add_column("users", sa.Column("analysis_prompt", sa.String(), nullable=True))


def downgrade() -> None:
    """Remove the custom analysis prompt."""
    op.drop_column("users", "analysis_prompt")
