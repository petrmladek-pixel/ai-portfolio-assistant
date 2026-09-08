"""Add AI analysis and chat cache tables.

Revision ID: c3d4e5f6a7b8
Revises: a7b8c9d0e1f2
Create Date: 2026-09-08 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create missing AI cache tables without modifying existing records."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("portfolio_analyses"):
        op.create_table(
            "portfolio_analyses",
            sa.Column("portfolio_id", sa.Integer(), nullable=False),
            sa.Column("rating_score", sa.Integer(), nullable=False),
            sa.Column("analysis_content", sa.String(), nullable=False),
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_portfolio_analyses_portfolio_id"),
            "portfolio_analyses",
            ["portfolio_id"],
            unique=False,
        )

    if not inspector.has_table("chat_messages"):
        op.create_table(
            "chat_messages",
            sa.Column("portfolio_id", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(), nullable=False),
            sa.Column("content", sa.String(), nullable=False),
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_chat_messages_portfolio_id"),
            "chat_messages",
            ["portfolio_id"],
            unique=False,
        )


def downgrade() -> None:
    """Keep AI cache data intact during a downgrade."""
