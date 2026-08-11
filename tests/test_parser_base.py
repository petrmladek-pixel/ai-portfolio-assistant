"""Tests for the base portfolio parser."""

from datetime import datetime
from decimal import Decimal

import pytest

from portfolio_assistant.models.portfolio import (
    Currency,
    ImportedPortfolio,
    StockPosition,
)
from portfolio_assistant.services.parser.base import BasePortfolioParser


class MockParser(BasePortfolioParser):
    """A mock parser for testing base class functionality."""

    @property
    def broker_name(self) -> str:
        return "MockBroker"

    async def parse(self, file_content: bytes) -> ImportedPortfolio:
        """Simple mock parsing logic."""
        # Just return a dummy portfolio for testing
        return ImportedPortfolio(
            broker_name=self.broker_name,
            imported_at=datetime.now(),
            positions=[
                StockPosition(
                    ticker="TSLA",
                    quantity=Decimal("1"),
                    average_price=Decimal("200"),
                    currency=Currency.USD,
                )
            ],
        )


def test_parser_broker_name():
    """Test the broker_name property."""
    parser = MockParser()
    assert parser.broker_name == "MockBroker"


@pytest.mark.asyncio
async def test_parse_async():
    """Test the asynchronous parse method."""
    parser = MockParser()
    portfolio = await parser.parse(b"dummy data")
    assert portfolio.broker_name == "MockBroker"
    assert len(portfolio.positions) == 1
    assert portfolio.positions[0].ticker == "TSLA"
