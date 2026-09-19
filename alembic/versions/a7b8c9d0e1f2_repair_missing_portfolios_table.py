"""Repair missing portfolios table in stamped SQLite databases.

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
Create Date: 2026-09-08 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | Sequence[str] | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the table only when a historical schema is incomplete."""
    bind = op.get_bind()
    if sa.inspect(bind).has_table("portfolios"):
        return

    op.create_table(
        "portfolios",
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("broker", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_portfolios_broker"),
        "portfolios",
        ["broker"],
        unique=False,
    )
    op.create_index(
        "uq_portfolios_user_id_name",
        "portfolios",
        ["user_id", "name"],
        unique=True,
    )
    op.create_index(
        op.f("ix_portfolios_name"),
        "portfolios",
        ["name"],
        unique=False,
    )


def downgrade() -> None:
    """Keep repaired data intact during a downgrade."""
