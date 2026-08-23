from datetime import date
from decimal import Decimal

from sqlmodel import Session, select

from portfolio_assistant.core import database
from portfolio_assistant.core.database import get_db_session
from portfolio_assistant.core.migrations import run_db_migrations
from portfolio_assistant.models.db_models import Portfolio, Position
from portfolio_assistant.models.user import User

# Reusing db_session from conftest.py


def test_create_and_read_user_portfolio_positions(db_session: Session):
    # 1. Create a User
    user = User(email="test@example.com", hashed_password="hashed_password_123")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.email == "test@example.com"

    # 2. Create a Portfolio for the user
    portfolio = Portfolio(
        name="My Retirement Portfolio",
        broker="Fio",
        user_id=user.id,
    )
    db_session.add(portfolio)
    db_session.commit()
    db_session.refresh(portfolio)

    assert portfolio.id is not None
    assert portfolio.user_id == user.id

    # 3. Create Positions in the portfolio
    pos1 = Position(
        asset_name="Apple Inc.",
        ticker="AAPL",
        isin="US0378331005",
        currency="USD",
        quantity=Decimal("10.50000000"),
        unit_cost=Decimal("175.25000000"),
        acquisition_date=date(2026, 1, 15),
        portfolio_id=portfolio.id,
    )
    pos2 = Position(
        asset_name="Tesla Inc.",
        ticker="TSLA",
        isin="US88160R1014",
        currency="USD",
        quantity=Decimal("5.00000000"),
        unit_cost=Decimal("200.00000000"),
        acquisition_date=date(2026, 2, 20),
        portfolio_id=portfolio.id,
    )
    db_session.add(pos1)
    db_session.add(pos2)
    db_session.commit()

    # 4. Query and Verify
    statement = select(Portfolio).where(Portfolio.id == portfolio.id)
    retrieved_portfolio = db_session.exec(statement).one()

    assert retrieved_portfolio.name == "My Retirement Portfolio"
    assert len(retrieved_portfolio.positions) == 2
    assert retrieved_portfolio.positions[0].ticker == "AAPL"
    assert retrieved_portfolio.positions[0].quantity == Decimal("10.50000000")
    assert retrieved_portfolio.positions[1].ticker == "TSLA"
    assert retrieved_portfolio.positions[1].quantity == Decimal("5.00000000")


def test_get_db_session():
    session_gen = get_db_session()
    session = next(session_gen)
    assert isinstance(session, Session)
    session.close()


def test_initialize_database_creates_schema(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, inspect

    database_url = f"sqlite:///{tmp_path / 'portfolio.db'}"
    monkeypatch.setattr(database, "SQLMODEL_DATABASE_URL", database_url)

    run_db_migrations()

    test_engine = create_engine(database_url)
    assert {"user", "portfolio", "position"} <= set(
        inspect(test_engine).get_table_names()
    )
