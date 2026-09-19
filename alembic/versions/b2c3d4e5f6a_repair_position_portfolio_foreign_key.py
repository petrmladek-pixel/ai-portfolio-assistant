"""Repair the position foreign key after a legacy portfolio table removal.

Revision ID: b2c3d4e5f6a
Revises: a1b2c3d4e5f6
Create Date: 2026-09-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2c3d4e5f6a"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Rebuild position when its foreign key references the legacy table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("position") or _references_portfolios(inspector):
        return

    op.rename_table("position", "position_legacy")
    _create_position_table()
    op.execute(
        sa.text(
            "INSERT INTO position "
            "(id, asset_name, ticker, isin, currency, quantity, unit_cost, "
            "acquisition_date, portfolio_id) "
            "SELECT legacy.id, legacy.asset_name, legacy.ticker, legacy.isin, "
            "legacy.currency, legacy.quantity, legacy.unit_cost, "
            "legacy.acquisition_date, canonical.id "
            "FROM position_legacy AS legacy "
            "LEFT JOIN portfolios AS canonical "
            "ON canonical.id = legacy.portfolio_id"
        )
    )
    op.drop_table("position_legacy")


def downgrade() -> None:
    """Require a database snapshot restore for an unsafe rollback request."""
    raise NotImplementedError(
        "This data-preserving migration cannot be safely downgraded. "
        "Restore a database snapshot taken before this migration instead."
    )


def _references_portfolios(inspector: sa.Inspector) -> bool:
    """Return whether position already references portfolios.id."""
    return any(
        foreign_key["constrained_columns"] == ["portfolio_id"]
        and foreign_key["referred_table"] == "portfolios"
        and foreign_key["referred_columns"] == ["id"]
        for foreign_key in inspector.get_foreign_keys("position")
    )


def _create_position_table() -> None:
    """Create position with the canonical portfolio foreign key."""
    op.create_table(
        "position",
        sa.Column("asset_name", sa.String(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("isin", sa.String(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("unit_cost", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("acquisition_date", sa.Date(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
