import os
from datetime import date
from decimal import Decimal

import pytest
from sqlmodel import Session, SQLModel, select

from portfolio_assistant.core.database import engine, get_db_session
from portfolio_assistant.models.db_models import Portfolio, Position
from portfolio_assistant.models.user import User


@pytest.fixture(name="db_session")
def db_session_fixture():
    # Setup - Ensure data directory exists
    os.makedirs("./data", exist_ok=True)
    # Setup - Use SQLModel to create tables
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    # Teardown - Drop tables after test
    SQLModel.metadata.drop_all(engine)


def test_create_and_read_user_portfolio_positions(db_session: Session):
    # 1. Create a User
    user = User(email="test@example.com", hashed_password="hashed_password_123")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.email == "test@example.com"

    # 2. Create a Portfolio for the user
    portfolio = Portfolio(name="My Retirement Portfolio", owner_id=user.id)
    db_session.add(portfolio)
    db_session.commit()
    db_session.refresh(portfolio)

    assert portfolio.id is not None
    assert portfolio.owner_id == user.id

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
