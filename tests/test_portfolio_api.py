"""Tests for portfolio persistence and retrieval."""

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session

from portfolio_assistant.dependencies import get_current_user
from portfolio_assistant.main import app
from portfolio_assistant.models.db_models import Portfolio, Position
from portfolio_assistant.models.user import User

client = TestClient(app)


def test_get_portfolio_me_empty(db_session: Session):
    """Test GET /api/portfolio/me when no portfolio exists."""
    mock_user = User(id=1, email="test@example.com", hashed_password="hash")
    app.dependency_overrides[get_current_user] = lambda: mock_user

    try:
        response = client.get("/api/portfolio/me")
        assert response.status_code == 200
        data = response.json()
        assert data["broker_name"] == "None"
        assert data["positions"] == []
    finally:
        app.dependency_overrides.clear()


def test_get_portfolio_me_with_data(db_session: Session):
    """Test GET /api/portfolio/me with saved data."""
    # Create test user
    user = User(email="test2@example.com", hashed_password="hash")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Create test portfolio
    portfolio = Portfolio(name="Fio", broker="Fio", user_id=user.id)
    db_session.add(portfolio)
    db_session.commit()
    db_session.refresh(portfolio)

    # Create test position
    position = Position(
        asset_name="Apple",
        ticker="AAPL",
        currency="USD",
        quantity=Decimal("10"),
        unit_cost=Decimal("150"),
        acquisition_date=date(2023, 1, 1),
        portfolio_id=portfolio.id,
    )
    db_session.add(position)
    db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: user

    try:
        response = client.get("/api/portfolio/me")
        assert response.status_code == 200
        data = response.json()
        assert data["broker_name"] == "Fio"
        assert len(data["positions"]) == 1
        assert data["positions"][0]["ticker"] == "AAPL"
        assert data["positions"][0]["quantity"] == 10.0
    finally:
        app.dependency_overrides.clear()


def test_post_portfolio_import(db_session: Session):
    """Test POST /api/portfolio/import with valid CSV file."""
    user = User(email="import_test@example.com", hashed_password="hash")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    portfolio = Portfolio(name="My Portfolio", broker="DEGIRO", user_id=user.id)
    db_session.add(portfolio)
    db_session.commit()
    db_session.refresh(portfolio)

    app.dependency_overrides[get_current_user] = lambda: user

    csv_content = (
        "Product,Symbol/ISIN,Quantity,Closing price,Currency\n"
        "Sony Group Corp,US8356993076,10,150.00,USD\n"
    )

    try:
        response = client.post(
            "/api/portfolio/import",
            data={
                "portfolio_id": str(portfolio.id),
                "import_type": "DEGIRO",
            },
            files={"file": ("portfolio.csv", csv_content.encode("utf-8"), "text/csv")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "successfully imported" in data["message"]
    finally:
        app.dependency_overrides.clear()
