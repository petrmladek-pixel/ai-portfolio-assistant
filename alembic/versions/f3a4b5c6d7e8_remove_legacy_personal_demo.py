"""Remove legacy demo copies from standard user portfolios.

Revision ID: f3a4b5c6d7e8
Revises: f2a3b4c5d6e7
Create Date: 2026-10-08
"""

import sqlalchemy as sa

from alembic import op

revision = "f3a4b5c6d7e8"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None

_DEMO_NAME = "Warren Buffett / Berkshire Hathaway Demo"
_DEMO_BROKER = "Berkshire Hathaway"
_LEGACY_TICKERS = ("AAPL", "AXP", "BAC", "CVX", "KO")


def upgrade() -> None:
    """Delete only the known five-position demo clone from standard accounts."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    required_tables = {"users", "portfolios", "positions"}
    if not required_tables <= set(inspector.get_table_names()):
        return
    required_columns = {
        "users": {"id", "is_demo"},
        "portfolios": {"id", "name", "broker", "user_id"},
        "positions": {"portfolio_id", "ticker"},
    }
    if any(
        not columns <= {column["name"] for column in inspector.get_columns(table)}
        for table, columns in required_columns.items()
    ):
        return

    portfolio_ids = bind.execute(_legacy_demo_statement()).scalars().all()
    for portfolio_id in portfolio_ids:
        bind.execute(
            sa.text("DELETE FROM positions WHERE portfolio_id = :portfolio_id"),
            {"portfolio_id": portfolio_id},
        )
        bind.execute(
            sa.text("DELETE FROM portfolios WHERE id = :portfolio_id"),
            {"portfolio_id": portfolio_id},
        )


def downgrade() -> None:
    """Require a database snapshot to restore removed legacy demo copies."""
    raise NotImplementedError(
        "This legacy-demo cleanup cannot be safely downgraded. "
        "Restore a database snapshot taken before this migration instead."
    )


def _legacy_demo_statement() -> sa.TextClause:
    """Select non-demo portfolios matching the complete historic demo signature."""
    ticker_params = ", ".join(f":ticker_{index}" for index in range(5))
    statement = sa.text(
        "SELECT portfolio.id "
        "FROM portfolios AS portfolio "
        "JOIN users AS owner ON owner.id = portfolio.user_id "
        "WHERE portfolio.name = :name "
        "AND portfolio.broker = :broker "
        "AND owner.is_demo = :is_demo "
        "AND (SELECT COUNT(*) FROM positions AS position "
        "WHERE position.portfolio_id = portfolio.id) = :position_count "
        "AND (SELECT COUNT(DISTINCT position.ticker) FROM positions AS position "
        "WHERE position.portfolio_id = portfolio.id) = :position_count "
        "AND NOT EXISTS (SELECT 1 FROM positions AS position "
        "WHERE position.portfolio_id = portfolio.id "
        f"AND position.ticker NOT IN ({ticker_params}))"
    )
    parameters = {
        "name": _DEMO_NAME,
        "broker": _DEMO_BROKER,
        "is_demo": False,
        "position_count": len(_LEGACY_TICKERS),
    }
    parameters.update(
        {f"ticker_{index}": ticker for index, ticker in enumerate(_LEGACY_TICKERS)}
    )
    return statement.bindparams(**parameters)
