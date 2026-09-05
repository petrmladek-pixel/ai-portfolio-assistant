"""Add transactions table.

Revision ID: e70c3b9a1d20
Revises: b8c70aa5a36c
Create Date: 2026-09-05 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e70c3b9a1d20"
down_revision: str | Sequence[str] | None = "b8c70aa5a36c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "transaction",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("transaction_type", sa.String(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolio.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_transaction_portfolio_id"),
        "transaction",
        ["portfolio_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_transaction_ticker"), "transaction", ["ticker"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_transaction_ticker"), table_name="transaction")
    op.drop_index(op.f("ix_transaction_portfolio_id"), table_name="transaction")
    op.drop_table("transaction")
