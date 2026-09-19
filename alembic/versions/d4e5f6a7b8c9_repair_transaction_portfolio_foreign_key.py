"""Repair transaction foreign key after portfolio table rename.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-19 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Keep canonical portfolios and repair transaction foreign keys."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("transaction") and not _references_portfolios(inspector):
        op.rename_table("transaction", "transaction_legacy")
        _create_transaction_table()
        op.execute(
            sa.text(
                'INSERT INTO "transaction" '
                "(id, ticker, quantity, transaction_type, portfolio_id) "
                "SELECT legacy.id, legacy.ticker, legacy.quantity, "
                "legacy.transaction_type, legacy.portfolio_id "
                "FROM transaction_legacy AS legacy "
                "JOIN portfolios AS canonical "
                "ON canonical.id = legacy.portfolio_id"
            )
        )
        op.drop_table("transaction_legacy")
        op.create_index(
            op.f("ix_transaction_portfolio_id"),
            "transaction",
            ["portfolio_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_transaction_ticker"),
            "transaction",
            ["ticker"],
            unique=False,
        )

    inspector = sa.inspect(bind)
    if inspector.has_table("portfolio"):
        op.drop_table("portfolio")


def downgrade() -> None:
    """Require a database snapshot restore for an unsafe rollback request."""
    raise NotImplementedError(
        "This data-preserving migration cannot be safely downgraded. "
        "Restore a database snapshot taken before this migration instead."
    )


def _references_portfolios(inspector: sa.Inspector) -> bool:
    """Return whether transaction already references portfolios.id."""
    foreign_keys = inspector.get_foreign_keys("transaction")
    return any(
        foreign_key["constrained_columns"] == ["portfolio_id"]
        and foreign_key["referred_table"] == "portfolios"
        and foreign_key["referred_columns"] == ["id"]
        for foreign_key in foreign_keys
    )


def _create_transaction_table() -> None:
    """Create transaction with the canonical portfolio foreign key."""
    op.create_table(
        "transaction",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("transaction_type", sa.String(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
