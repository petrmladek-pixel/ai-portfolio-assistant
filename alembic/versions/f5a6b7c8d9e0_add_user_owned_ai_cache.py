"""Associate strategic analysis cache records with their users.

Revision ID: f5a6b7c8d9e0
Revises: f4a5b6c7d8e9
Create Date: 2026-10-09
"""

import sqlalchemy as sa

from alembic import op

revision = "f5a6b7c8d9e0"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Backfill cache ownership from each legacy source portfolio."""
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("portfolio_ai_analyses"):
        return
    columns = {
        column["name"] for column in inspector.get_columns("portfolio_ai_analyses")
    }
    if "user_id" not in columns:
        op.add_column(
            "portfolio_ai_analyses",
            sa.Column("user_id", sa.Integer(), nullable=True),
        )
        op.create_index(
            "ix_portfolio_ai_analyses_user_id",
            "portfolio_ai_analyses",
            ["user_id"],
            unique=False,
        )
    op.execute(
        sa.text(
            "UPDATE portfolio_ai_analyses AS analysis "
            "SET user_id = (SELECT portfolio.user_id FROM portfolios AS portfolio "
            "WHERE portfolio.id = analysis.portfolio_id) "
            "WHERE analysis.user_id IS NULL"
        )
    )


def downgrade() -> None:
    """Remove user-owned cache lookup support."""
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("portfolio_ai_analyses"):
        return
    indexes = {
        index["name"] for index in inspector.get_indexes("portfolio_ai_analyses")
    }
    if "ix_portfolio_ai_analyses_user_id" in indexes:
        op.drop_index("ix_portfolio_ai_analyses_user_id", "portfolio_ai_analyses")
    columns = {
        column["name"] for column in inspector.get_columns("portfolio_ai_analyses")
    }
    if "user_id" in columns:
        op.drop_column("portfolio_ai_analyses", "user_id")
