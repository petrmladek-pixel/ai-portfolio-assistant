"""Tests for the one-click Buffett demo portfolio workflow."""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from portfolio_assistant.core.database import get_db_session
from portfolio_assistant.dependencies import get_current_user
from portfolio_assistant.main import app
from portfolio_assistant.models.db_models import Portfolio, Position
from portfolio_assistant.models.portfolio import (
    Currency,
    ImportedPortfolio,
    StockPosition,
)
from portfolio_assistant.models.user import User
from portfolio_assistant.services.valuation.engine import ValuationService

client = TestClient(app)


def test_public_demo_allocations_are_available_without_authentication() -> None:
    """Anonymous visitors can load the expanded dashboard demo allocations."""
    response = client.get("/api/portfolios/demo/allocations")

    assert response.status_code == 200
    payload = response.json()
    assert payload["portfolio_id"] is None
    assert len(payload["allocations"]) >= 20
    assert Decimal(payload["total_value"]) > Decimal("0")


def test_post_demo_creates_valued_portfolio_and_allocations(
    db_session: Session,
) -> None:
    """The demo endpoint creates valid positions usable by both calculations."""
    user = User(email="demo-seeder@example.com", hashed_password="hash")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: db_session

    try:
        response = client.post("/api/portfolios/demo")
        assert response.status_code == 201
        payload = response.json()
        assert payload["status"] == "success"
        assert payload["redirect_url"] == (
            f"/dashboard?portfolio_id={payload['portfolio_id']}"
        )
        repeat_response = client.post("/api/portfolios/demo")
        assert repeat_response.status_code == 201
        assert repeat_response.json()["portfolio_id"] == payload["portfolio_id"]

        portfolio = db_session.exec(
            select(Portfolio).where(Portfolio.id == payload["portfolio_id"])
        ).one()
        positions = db_session.exec(
            select(Position).where(Position.portfolio_id == portfolio.id)
        ).all()
        assert portfolio.user_id == user.id
        assert len(positions) >= 20
        assert {"AAPL", "BAC", "AXP", "KO", "CVX"} <= {
            position.ticker for position in positions
        }
        personal_portfolio = Portfolio(
            name="Personal Portfolio",
            broker="Test Broker",
            user_id=user.id,
        )
        db_session.add(personal_portfolio)
        db_session.commit()
        db_session.refresh(personal_portfolio)
        db_session.add(
            Position(
                asset_name="Test Asset",
                ticker="TEST",
                currency="USD",
                quantity=Decimal("2"),
                unit_cost=Decimal("100"),
                acquisition_date=datetime.now(UTC).date(),
                portfolio_id=personal_portfolio.id,
            )
        )
        db_session.commit()
        prices = {position.ticker: position.unit_cost for position in positions}
        prices["TEST"] = Decimal("100")

        imported = ImportedPortfolio(
            broker_name=portfolio.name,
            imported_at=datetime.now(UTC),
            positions=[
                StockPosition(
                    ticker=position.ticker,
                    name=position.asset_name,
                    quantity=position.quantity,
                    average_price=position.unit_cost,
                    currency=Currency(position.currency),
                )
                for position in positions
            ],
        )
        market_data = AsyncMock()
        market_data.get_current_prices.return_value = prices
        market_data.get_exchange_rate.return_value = Decimal("1")
        valued = asyncio.run(
            ValuationService(market_data).value_portfolio_async(imported)
        )
        assert isinstance(valued.total_value, Decimal)
        assert valued.total_value > Decimal("0")

        with (
            patch(
                "portfolio_assistant.services.allocation."
                "PriceCacheService.get_current_prices",
                return_value=prices,
            ),
            patch(
                "portfolio_assistant.services.allocation."
                "MetadataCacheService.get_tickers_metadata",
                return_value={},
            ),
            patch(
                "portfolio_assistant.services.allocation."
                "YFinanceMarketDataService.get_exchange_rate",
                new_callable=AsyncMock,
                return_value=Decimal("1"),
            ),
        ):
            allocation_response = client.get(
                f"/api/portfolios/{portfolio.id}/allocations"
            )
            all_response = client.get("/api/portfolios/all/allocations")
        assert allocation_response.status_code == 200
        allocation_data = allocation_response.json()
        assert Decimal(allocation_data["total_value"]) > Decimal("0")
        assert len(allocation_data["allocations"]) == len(prices) - 1
        assert all_response.status_code == 200
        assert [item["ticker"] for item in all_response.json()["allocations"]] == [
            "TEST"
        ]
    finally:
        app.dependency_overrides.clear()
