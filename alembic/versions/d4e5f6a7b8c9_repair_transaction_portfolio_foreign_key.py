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
    """Preserve legacy portfolios and point transactions at the canonical table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    _migrate_legacy_portfolios(bind, inspector)
    inspector = sa.inspect(bind)
    if not inspector.has_table("transaction"):
        return
    if _references_portfolios(inspector):
        return

    op.rename_table("transaction", "transaction_legacy")
    _create_transaction_table()
    op.execute(
        sa.text(
            'INSERT INTO "transaction" '
            "(id, ticker, quantity, transaction_type, portfolio_id) "
            "SELECT id, ticker, quantity, transaction_type, portfolio_id "
            "FROM transaction_legacy"
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


def _migrate_legacy_portfolios(bind: sa.Connection, inspector: sa.Inspector) -> None:
    """Copy a legacy singular table after the historical repair created plural."""
    if not inspector.has_table("portfolio"):
        return
    if not inspector.has_table("portfolios"):
        raise RuntimeError("Canonical portfolios table is missing.")

    conflict = bind.execute(
        sa.text(
            "SELECT legacy.id FROM portfolio AS legacy "
            "JOIN portfolios AS canonical ON canonical.id = legacy.id "
            "WHERE canonical.name IS NOT legacy.name "
            "OR canonical.broker IS NOT legacy.broker "
            "OR canonical.description IS NOT legacy.description "
            "OR canonical.user_id IS NOT legacy.user_id LIMIT 1"
        )
    ).scalar_one_or_none()
    if conflict is not None:
        raise RuntimeError(
            "Cannot migrate legacy portfolio data because portfolio IDs conflict."
        )

    bind.execute(
        sa.text(
            "INSERT INTO portfolios (id, name, broker, description, user_id) "
            "SELECT legacy.id, legacy.name, legacy.broker, legacy.description, "
            "legacy.user_id FROM portfolio AS legacy "
            "WHERE NOT EXISTS (SELECT 1 FROM portfolios AS canonical "
            "WHERE canonical.id = legacy.id)"
        )
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
