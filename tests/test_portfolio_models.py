"""Tests for portfolio Pydantic models."""

from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from portfolio_assistant.models.portfolio import (
    Currency,
    ImportedPortfolio,
    StockPosition,
)


def test_stock_position_valid():
    """Test creating a valid StockPosition."""
    pos = StockPosition(
        ticker=" aapl ",
        name="Apple Inc.",
        quantity=Decimal("10.5"),
        average_price=Decimal("150.25"),
        currency=Currency.USD,
    )
    assert pos.ticker == "AAPL"
    assert pos.quantity == Decimal("10.5")
    assert pos.average_price == Decimal("150.25")


def test_stock_position_invalid_ticker():
    """Test StockPosition with invalid ticker values."""
    # Empty string
    with pytest.raises(ValidationError):
        StockPosition(
            ticker="",
            quantity=Decimal("1"),
            average_price=Decimal("1"),
            currency=Currency.USD,
        )

    # Whitespace only
    with pytest.raises(ValidationError):
        StockPosition(
            ticker="   ",
            quantity=Decimal("1"),
            average_price=Decimal("1"),
            currency=Currency.USD,
        )


def test_stock_position_invalid_numbers():
    """Test StockPosition with non-positive numbers."""
    with pytest.raises(ValidationError):
        StockPosition(
            ticker="AAPL",
            quantity=Decimal("0"),
            average_price=Decimal("1"),
            currency=Currency.USD,
        )

    with pytest.raises(ValidationError):
        StockPosition(
            ticker="AAPL",
            quantity=Decimal("1"),
            average_price=Decimal("-1"),
            currency=Currency.USD,
        )


def test_imported_portfolio_valid():
    """Test creating a valid ImportedPortfolio."""
    pos = StockPosition(
        ticker="MSFT",
        quantity=Decimal("5"),
        average_price=Decimal("300"),
        currency=Currency.USD,
    )
    portfolio = ImportedPortfolio(
        broker_name=" DEGIRO ",
        imported_at=datetime.now(),
        positions=[pos],
    )
    assert portfolio.broker_name == "DEGIRO"
    assert len(portfolio.positions) == 1
    assert portfolio.positions[0].ticker == "MSFT"


def test_imported_portfolio_invalid_broker():
    """Test ImportedPortfolio with invalid broker name."""
    with pytest.raises(ValidationError):
        ImportedPortfolio(
            broker_name="  ",
            imported_at=datetime.now(),
            positions=[],
        )
