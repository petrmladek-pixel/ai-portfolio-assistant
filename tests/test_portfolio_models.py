"""Tests for portfolio Pydantic models."""

from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from portfolio_assistant.models.portfolio import (
    AnonymizedPortfolio,
    AnonymizedPosition,
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


def test_anonymized_position_valid():
    """Test creating a valid AnonymizedPosition."""
    pos = AnonymizedPosition(
        ticker=" tsla ",
        name="Tesla Inc.",
        weight=Decimal("0.25"),
        currency=Currency.USD,
    )
    assert pos.ticker == "TSLA"
    assert pos.weight == Decimal("0.25")


def test_anonymized_position_invalid_weight():
    """Test AnonymizedPosition with invalid weight values."""
    # Weight <= 0
    with pytest.raises(ValidationError):
        AnonymizedPosition(
            ticker="AAPL",
            weight=Decimal("0"),
            currency=Currency.USD,
        )

    # Weight > 1
    with pytest.raises(ValidationError):
        AnonymizedPosition(
            ticker="AAPL",
            weight=Decimal("1.0001"),
            currency=Currency.USD,
        )


def test_to_anonymized_calculation():
    """Test the to_anonymized method calculation and output."""
    now = datetime.now()
    pos1 = StockPosition(
        ticker="AAPL",
        quantity=Decimal("10"),
        average_price=Decimal("150"),  # Value: 1500
        currency=Currency.USD,
    )
    pos2 = StockPosition(
        ticker="MSFT",
        quantity=Decimal("5"),
        average_price=Decimal("300"),  # Value: 1500
        currency=Currency.USD,
    )
    # Total value = 3000, each weight should be 0.5

    portfolio = ImportedPortfolio(
        broker_name="TestBroker",
        imported_at=now,
        positions=[pos1, pos2],
    )

    anonymized = portfolio.to_anonymized()

    assert isinstance(anonymized, AnonymizedPortfolio)
    assert anonymized.broker_name == "TestBroker"
    assert anonymized.imported_at == now
    assert len(anonymized.positions) == 2

    # Verify weights
    weights = {p.ticker: p.weight for p in anonymized.positions}
    assert weights["AAPL"] == Decimal("0.5")
    assert weights["MSFT"] == Decimal("0.5")


def test_to_anonymized_empty():
    """Test to_anonymized with an empty portfolio."""
    portfolio = ImportedPortfolio(
        broker_name="Empty",
        imported_at=datetime.now(),
        positions=[],
    )
    anonymized = portfolio.to_anonymized()
    assert len(anonymized.positions) == 0
