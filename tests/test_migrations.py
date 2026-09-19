"""Integration tests for data-preserving Alembic migrations."""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command
from portfolio_assistant.core import database

LEGACY_REVISION = "f1a2b3c4d5e6"


def test_upgrade_creates_the_normalized_schema_from_an_empty_database(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Create only plural tables and strict portfolio relationships."""
    database_url = f"sqlite:///{tmp_path / 'empty.db'}"
    monkeypatch.setattr(database, "SQLMODEL_DATABASE_URL", database_url)

    command.upgrade(Config("alembic.ini"), "head")

    inspector = inspect(create_engine(database_url))
    table_names = set(inspector.get_table_names())
    assert {"users", "portfolios", "positions", "transactions"} <= table_names
    assert not {"user", "position", "transaction"} & table_names
    position_columns = {
        column["name"]: column for column in inspector.get_columns("positions")
    }
    assert position_columns["portfolio_id"]["nullable"] is False
    assert position_columns["quantity"]["nullable"] is False
    assert position_columns["unit_cost"]["nullable"] is False
    assert _position_references_portfolios(inspector)


def test_upgrade_discards_legacy_portfolio_and_transactions(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Discard singular-table data when it has no canonical portfolio."""
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
            text("SELECT COUNT(*) FROM transactions")
        ).scalar_one()

    assert "portfolio" not in inspector.get_table_names()
    assert {"users", "portfolios", "transactions"} <= set(inspector.get_table_names())
    assert portfolio_count == 0
    assert transaction_count == 0
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


def test_upgrade_prefers_canonical_portfolio_when_legacy_id_conflicts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Keep canonical data and remove the conflicting singular legacy table."""
    database_url = f"sqlite:///{tmp_path / 'conflict.db'}"
    _create_conflicting_portfolio_database(database_url)
    monkeypatch.setattr(database, "SQLMODEL_DATABASE_URL", database_url)

    command.upgrade(Config("alembic.ini"), "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    with engine.connect() as connection:
        portfolio = connection.execute(
            text("SELECT name, broker FROM portfolios WHERE id = 1")
        ).one()
        transaction_count = connection.execute(
            text("SELECT COUNT(*) FROM transactions")
        ).scalar_one()

    assert "portfolio" not in inspector.get_table_names()
    assert portfolio == ("Canonical", "DEGIRO")
    assert transaction_count == 1


def test_upgrade_repairs_position_foreign_key_after_legacy_drop(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Preserve positions while replacing a missing legacy foreign key target."""
    database_url = f"sqlite:///{tmp_path / 'position-fk.db'}"
    _create_database_with_broken_position_foreign_key(database_url)
    monkeypatch.setattr(database, "SQLMODEL_DATABASE_URL", database_url)

    command.upgrade(Config("alembic.ini"), "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    with engine.connect() as connection:
        position = connection.execute(
            text("SELECT ticker, portfolio_id FROM positions WHERE id = 1")
        ).one()

    assert position == ("AAPL", 1)
    assert _position_references_portfolios(inspector)
    portfolio_id = next(
        column
        for column in inspector.get_columns("positions")
        if column["name"] == "portfolio_id"
    )
    assert portfolio_id["nullable"] is False


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
    """Reject unsafe rollback without restoring discarded legacy portfolio data."""
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

    assert portfolio_count == 0


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


def _create_conflicting_portfolio_database(database_url: str) -> None:
    """Create canonical and legacy portfolio tables with one conflicting ID."""
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE "user" (id INTEGER PRIMARY KEY)'))
        for table in ("portfolio", "portfolios"):
            connection.execute(
                text(
                    f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, name VARCHAR "
                    "NOT NULL, broker VARCHAR NOT NULL, description VARCHAR, "
                    "user_id INTEGER)"
                )
            )
        connection.execute(
            text(
                'CREATE TABLE "transaction" (id INTEGER PRIMARY KEY, '
                "ticker VARCHAR NOT NULL, quantity NUMERIC NOT NULL, "
                "transaction_type VARCHAR NOT NULL, portfolio_id INTEGER NOT NULL, "
                "FOREIGN KEY(portfolio_id) REFERENCES portfolio (id))"
            )
        )
        connection.execute(
            text("INSERT INTO portfolio (id, name, broker) VALUES (1, 'Legacy', 'Fio')")
        )
        connection.execute(
            text(
                "INSERT INTO portfolios (id, name, broker) "
                "VALUES (1, 'Canonical', 'DEGIRO')"
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


def _create_database_with_broken_position_foreign_key(database_url: str) -> None:
    """Create a current database where position references a missing table."""
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE portfolios (id INTEGER PRIMARY KEY, name VARCHAR "
                "NOT NULL, broker VARCHAR NOT NULL)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE position (asset_name VARCHAR NOT NULL, "
                "ticker VARCHAR NOT NULL, isin VARCHAR, currency VARCHAR NOT NULL, "
                "quantity NUMERIC, unit_cost NUMERIC, acquisition_date DATE NOT NULL, "
                "portfolio_id INTEGER, id INTEGER PRIMARY KEY, "
                "FOREIGN KEY(portfolio_id) REFERENCES portfolio (id))"
            )
        )
        connection.execute(
            text("INSERT INTO portfolios (id, name, broker) VALUES (1, 'Core', 'Fio')")
        )
        connection.execute(
            text(
                "INSERT INTO position "
                "(id, asset_name, ticker, currency, quantity, unit_cost, "
                "acquisition_date, portfolio_id) "
                "VALUES (1, 'Apple Inc.', 'AAPL', 'USD', 1, 100, '2026-01-01', 1)"
            )
        )
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR)"))
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
            {"revision": "a1b2c3d4e5f6"},
        )


def _transaction_references_portfolios(inspector) -> bool:
    """Return whether transaction has the expected canonical foreign key."""
    foreign_keys = inspector.get_foreign_keys("transactions")
    return any(
        foreign_key["constrained_columns"] == ["portfolio_id"]
        and foreign_key["referred_table"] == "portfolios"
        and foreign_key["referred_columns"] == ["id"]
        for foreign_key in foreign_keys
    )


def _position_references_portfolios(inspector) -> bool:
    """Return whether position has the expected canonical foreign key."""
    foreign_keys = inspector.get_foreign_keys("positions")
    return any(
        foreign_key["constrained_columns"] == ["portfolio_id"]
        and foreign_key["referred_table"] == "portfolios"
        and foreign_key["referred_columns"] == ["id"]
        for foreign_key in foreign_keys
    )
