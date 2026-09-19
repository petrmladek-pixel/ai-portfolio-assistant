"""Add persona-aware AI analysis cache table.

Revision ID: a1b2c3d4e5f6
Revises: d4e5f6a7b8c9
Create Date: 2026-09-19
"""

import sqlalchemy as sa

from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the persona-aware analysis cache table."""
    op.create_table(
        "portfolio_ai_analyses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("analysis_text", sa.String(), nullable=False),
        sa.Column("persona_id", sa.String(), nullable=False),
        sa.Column("user_context", sa.String(), nullable=True),
        sa.Column("portfolio_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_portfolio_ai_analyses_persona_id"),
        "portfolio_ai_analyses",
        ["persona_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_portfolio_ai_analyses_portfolio_id"),
        "portfolio_ai_analyses",
        ["portfolio_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the persona-aware analysis cache table."""
    op.drop_index(
        op.f("ix_portfolio_ai_analyses_portfolio_id"),
        table_name="portfolio_ai_analyses",
    )
    op.drop_index(
        op.f("ix_portfolio_ai_analyses_persona_id"),
        table_name="portfolio_ai_analyses",
    )
    op.drop_table("portfolio_ai_analyses")
