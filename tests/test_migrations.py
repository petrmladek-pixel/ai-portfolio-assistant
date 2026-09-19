"""Integration tests for data-preserving Alembic migrations."""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command
from portfolio_assistant.core import database

LEGACY_REVISION = "f1a2b3c4d5e6"


def test_upgrade_migrates_legacy_portfolio_and_preserves_records(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Upgrade a legacy schema without losing portfolio or transaction data."""
    database_url = f"sqlite:///{tmp_path / 'legacy.db'}"
    _create_database_with_portfolio_table(database_url, "portfolio")
    monkeypatch.setattr(database, "SQLMODEL_DATABASE_URL", database_url)

    command.upgrade(Config("alembic.ini"), "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    with engine.connect() as connection:
        portfolio_count = connection.execute(
            text("SELECT COUNT(*) FROM portfolios")
        ).scalar_one()
        transaction_count = connection.execute(
            text('SELECT COUNT(*) FROM "transaction"')
        ).scalar_one()

    assert "portfolio" in inspector.get_table_names()
    assert portfolio_count == 1
    assert transaction_count == 1
    assert _transaction_references_portfolios(inspector)


def test_upgrade_keeps_existing_portfolios_records(tmp_path: Path, monkeypatch) -> None:
    """Leave canonical portfolio records intact while repairing transactions."""
    database_url = f"sqlite:///{tmp_path / 'canonical.db'}"
    _create_database_with_portfolio_table(database_url, "portfolios")
    monkeypatch.setattr(database, "SQLMODEL_DATABASE_URL", database_url)

    command.upgrade(Config("alembic.ini"), "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    with engine.connect() as connection:
        portfolio_count = connection.execute(
            text("SELECT COUNT(*) FROM portfolios")
        ).scalar_one()

    assert portfolio_count == 1
    assert _transaction_references_portfolios(inspector)


def test_upgrade_creates_missing_portfolios_table(tmp_path: Path, monkeypatch) -> None:
    """Create portfolios when a stamped database has no portfolio table."""
    database_url = f"sqlite:///{tmp_path / 'missing.db'}"
    _create_stamped_database(database_url)
    monkeypatch.setattr(database, "SQLMODEL_DATABASE_URL", database_url)

    command.upgrade(Config("alembic.ini"), "head")

    assert "portfolios" in inspect(create_engine(database_url)).get_table_names()


def test_downgrade_fails_without_changing_migrated_data(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Reject unsafe schema rollback after preserving legacy portfolio records."""
    database_url = f"sqlite:///{tmp_path / 'downgrade.db'}"
    _create_database_with_portfolio_table(database_url, "portfolio")
    monkeypatch.setattr(database, "SQLMODEL_DATABASE_URL", database_url)
    config = Config("alembic.ini")
    command.upgrade(config, "head")

    with pytest.raises(NotImplementedError, match="cannot be safely downgraded"):
        command.downgrade(config, "c3d4e5f6a7b8")

    with create_engine(database_url).connect() as connection:
        portfolio_count = connection.execute(
            text("SELECT COUNT(*) FROM portfolios")
        ).scalar_one()

    assert portfolio_count == 1


def _create_database_with_portfolio_table(
    database_url: str,
    portfolio_table: str,
) -> None:
    """Create a stamped schema with a portfolio table and sample records."""
    if portfolio_table not in {"portfolio", "portfolios"}:
        raise ValueError("Unsupported portfolio table name.")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE "user" (id INTEGER PRIMARY KEY)'))
        connection.execute(
            text(
                f"CREATE TABLE {portfolio_table} (id INTEGER PRIMARY KEY, "
                "name VARCHAR "
                "NOT NULL, broker VARCHAR NOT NULL, description VARCHAR, "
                "user_id INTEGER)"
            )
        )
        connection.execute(
            text(
                'CREATE TABLE "transaction" (id INTEGER PRIMARY KEY, '
                "ticker VARCHAR NOT NULL, quantity NUMERIC NOT NULL, "
                "transaction_type VARCHAR NOT NULL, portfolio_id INTEGER NOT NULL, "
                f"FOREIGN KEY(portfolio_id) REFERENCES {portfolio_table} (id))"
            )
        )
        connection.execute(
            text(
                f"INSERT INTO {portfolio_table} (id, name, broker) "
                "VALUES (1, 'Long term', 'Fio')"
            )
        )
        connection.execute(
            text(
                'INSERT INTO "transaction" '
                "(id, ticker, quantity, transaction_type, portfolio_id) "
                "VALUES (1, 'AAPL', 1, 'buy', 1)"
            )
        )
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR)"))
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
            {"revision": LEGACY_REVISION},
        )


def _create_stamped_database(database_url: str) -> None:
    """Create a historical database marked as migrated but missing portfolios."""
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE "user" (id INTEGER PRIMARY KEY)'))
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR)"))
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
            {"revision": LEGACY_REVISION},
        )


def _transaction_references_portfolios(inspector) -> bool:
    """Return whether transaction has the expected canonical foreign key."""
    foreign_keys = inspector.get_foreign_keys("transaction")
    return any(
        foreign_key["constrained_columns"] == ["portfolio_id"]
        and foreign_key["referred_table"] == "portfolios"
        and foreign_key["referred_columns"] == ["id"]
        for foreign_key in foreign_keys
    )
