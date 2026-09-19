"""Normalize database table names and portfolio relationships.

Revision ID: c3d4e5f6a7b
Revises: b2c3d4e5f6a
Create Date: 2026-09-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3d4e5f6a7b"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Use plural table names and require every position to have a portfolio."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    _rename_user_table(inspector)
    inspector = sa.inspect(bind)
    _add_portfolio_name_constraint(bind, inspector)
    _replace_position_table(inspector)
    _replace_transaction_table(inspector)


def downgrade() -> None:
    """Require a database snapshot restore for an unsafe rollback request."""
    raise NotImplementedError(
        "This data-cleanup migration cannot be safely downgraded. "
        "Restore a database snapshot taken before this migration instead."
    )


def _rename_user_table(inspector: sa.Inspector) -> None:
    """Rename the legacy user table and give its email index a plural name."""
    has_legacy = inspector.has_table("user")
    has_canonical = inspector.has_table("users")
    if has_legacy and has_canonical:
        raise RuntimeError("Both user and users tables exist.")
    if not has_legacy:
        return

    op.rename_table("user", "users")
    columns = sa.inspect(op.get_bind()).get_columns("users")
    if not any(column["name"] == "email" for column in columns):
        return
    for index in sa.inspect(op.get_bind()).get_indexes("users"):
        if index["name"] == "ix_user_email":
            op.drop_index("ix_user_email", table_name="users")
            break
    op.create_index("ix_users_email", "users", ["email"], unique=True)


def _add_portfolio_name_constraint(
    bind: sa.Connection,
    inspector: sa.Inspector,
) -> None:
    """Prevent duplicate portfolio names for the same user."""
    columns = inspector.get_columns("portfolios")
    column_names = {column["name"] for column in columns}
    if not {"user_id", "name"} <= column_names:
        return
    duplicate = bind.execute(
        sa.text(
            "SELECT user_id, name FROM portfolios "
            "GROUP BY user_id, name HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).one_or_none()
    if duplicate is not None:
        raise RuntimeError("Duplicate portfolio names exist for one user.")
    if any(
        index["name"] == "uq_portfolios_user_id_name"
        for index in inspector.get_indexes("portfolios")
    ):
        return
    op.create_index(
        "uq_portfolios_user_id_name",
        "portfolios",
        ["user_id", "name"],
        unique=True,
    )


def _replace_position_table(inspector: sa.Inspector) -> None:
    """Create plural positions and discard records without a canonical portfolio."""
    if not inspector.has_table("position"):
        return
    if inspector.has_table("positions"):
        raise RuntimeError("Both position and positions tables exist.")

    op.rename_table("position", "position_legacy")
    op.create_table(
        "positions",
        sa.Column("asset_name", sa.String(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("isin", sa.String(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("acquisition_date", sa.Date(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        sa.text(
            "INSERT INTO positions "
            "(id, asset_name, ticker, isin, currency, quantity, unit_cost, "
            "acquisition_date, portfolio_id) "
            "SELECT legacy.id, legacy.asset_name, legacy.ticker, legacy.isin, "
            "legacy.currency, legacy.quantity, legacy.unit_cost, "
            "legacy.acquisition_date, legacy.portfolio_id "
            "FROM position_legacy AS legacy "
            "JOIN portfolios AS portfolio ON portfolio.id = legacy.portfolio_id "
            "WHERE legacy.quantity IS NOT NULL AND legacy.unit_cost IS NOT NULL"
        )
    )
    op.drop_table("position_legacy")


def _replace_transaction_table(inspector: sa.Inspector) -> None:
    """Create plural transactions while preserving valid canonical records."""
    if not inspector.has_table("transaction"):
        return
    if inspector.has_table("transactions"):
        raise RuntimeError("Both transaction and transactions tables exist.")

    op.rename_table("transaction", "transaction_legacy")
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("transaction_type", sa.String(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        sa.text(
            "INSERT INTO transactions "
            "(id, ticker, quantity, transaction_type, portfolio_id) "
            "SELECT legacy.id, legacy.ticker, legacy.quantity, "
            "legacy.transaction_type, legacy.portfolio_id "
            "FROM transaction_legacy AS legacy "
            "JOIN portfolios AS portfolio ON portfolio.id = legacy.portfolio_id"
        )
    )
    op.drop_table("transaction_legacy")
    op.create_index("ix_transactions_portfolio_id", "transactions", ["portfolio_id"])
    op.create_index("ix_transactions_ticker", "transactions", ["ticker"])
