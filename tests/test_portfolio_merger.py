"""Tests for the portfolio merger functionality."""

from datetime import datetime
from decimal import Decimal

import pytest

from portfolio_assistant.models.portfolio import (
    Currency,
    ImportedPortfolio,
    StockPosition,
)
from portfolio_assistant.services.portfolio_merger import PortfolioMerger


@pytest.fixture
def portfolio_merger():
    """Fixture for creating a portfolio merger instance."""
    return PortfolioMerger()


@pytest.fixture
def sample_portfolio_a():
    """Fixture for creating a sample portfolio A."""
    return ImportedPortfolio(
        broker_name="BrokerA",
        imported_at=datetime(2023, 1, 1, 12, 0, 0),
        positions=[
            StockPosition(
                ticker="AAPL",
                name="Apple Inc.",
                quantity=Decimal("10"),
                average_price=Decimal("150.00"),
                currency=Currency.USD,
            ),
            StockPosition(
                ticker="MSFT",
                name="Microsoft Corp.",
                quantity=Decimal("5"),
                average_price=Decimal("300.00"),
                currency=Currency.USD,
            ),
            StockPosition(
                ticker="UNKNOWN",
                name="Unknown Asset 1",
                quantity=Decimal("2"),
                average_price=Decimal("100.00"),
                currency=Currency.USD,
            ),
        ],
    )


@pytest.fixture
def sample_portfolio_b():
    """Fixture for creating a sample portfolio B."""
    return ImportedPortfolio(
        broker_name="BrokerB",
        imported_at=datetime(2023, 1, 1, 12, 0, 0),
        positions=[
            StockPosition(
                ticker="AAPL",
                name="Apple Inc.",
                quantity=Decimal("15"),
                average_price=Decimal("160.00"),
                currency=Currency.USD,
            ),
            StockPosition(
                ticker="GOOGL",
                name="Alphabet Inc.",
                quantity=Decimal("3"),
                average_price=Decimal("2500.00"),
                currency=Currency.USD,
            ),
            StockPosition(
                ticker="UNKNOWN",
                name="Unknown Asset 2",
                quantity=Decimal("1"),
                average_price=Decimal("200.00"),
                currency=Currency.USD,
            ),
        ],
    )


def test_portfolio_merger_empty_list(portfolio_merger):
    """Test that portfolio merger handles empty list correctly."""
    with pytest.raises(ValueError, match="No portfolios provided for merging"):
        portfolio_merger.merge_portfolios([])


def test_portfolio_merger_single_portfolio(portfolio_merger, sample_portfolio_a):
    """Test that portfolio merger handles single portfolio correctly."""
    merged_portfolio = portfolio_merger.merge_portfolios([sample_portfolio_a])

    assert merged_portfolio.broker_name == "MERGED"
    assert merged_portfolio.imported_at == sample_portfolio_a.imported_at
    assert len(merged_portfolio.positions) == 3

    # Verify positions are unchanged
    for i, position in enumerate(merged_portfolio.positions):
        assert position.ticker == sample_portfolio_a.positions[i].ticker
        assert position.name == sample_portfolio_a.positions[i].name
        assert position.quantity == sample_portfolio_a.positions[i].quantity
        assert position.average_price == sample_portfolio_a.positions[i].average_price
        assert position.currency == sample_portfolio_a.positions[i].currency


def test_portfolio_merger_multiple_portfolios(
    portfolio_merger, sample_portfolio_a, sample_portfolio_b
):
    """Test merging multiple portfolios with overlapping and unique positions."""
    merged_portfolio = portfolio_merger.merge_portfolios(
        [sample_portfolio_a, sample_portfolio_b]
    )

    assert merged_portfolio.broker_name == "MERGED"
    assert merged_portfolio.imported_at == sample_portfolio_a.imported_at

    # Should have: AAPL (merged), MSFT, GOOGL, UNKNOWN_0, UNKNOWN_1
    assert len(merged_portfolio.positions) == 5

    # Find and verify merged AAPL position
    aapl_position = next(p for p in merged_portfolio.positions if p.ticker == "AAPL")
    assert aapl_position.name == "Apple Inc."
    assert aapl_position.quantity == Decimal("25")  # 10 + 15
    assert aapl_position.currency == Currency.USD

    # Calculate expected weighted average price:
    # (10 * 150 + 15 * 160) / 25 = (1500 + 2400) / 25 = 3900 / 25 = 156.00
    assert aapl_position.average_price == Decimal("156.00")

    # Verify MSFT position (only in portfolio A)
    msft_position = next(p for p in merged_portfolio.positions if p.ticker == "MSFT")
    assert msft_position.name == "Microsoft Corp."
    assert msft_position.quantity == Decimal("5")
    assert msft_position.average_price == Decimal("300.00")
    assert msft_position.currency == Currency.USD

    # Verify GOOGL position (only in portfolio B)
    googl_position = next(p for p in merged_portfolio.positions if p.ticker == "GOOGL")
    assert googl_position.name == "Alphabet Inc."
    assert googl_position.quantity == Decimal("3")
    assert googl_position.average_price == Decimal("2500.00")
    assert googl_position.currency == Currency.USD


def test_portfolio_merger_unknown_positions_separate(
    portfolio_merger, sample_portfolio_a, sample_portfolio_b
):
    """Test that unknown positions are kept separate."""
    merged_portfolio = portfolio_merger.merge_portfolios(
        [sample_portfolio_a, sample_portfolio_b]
    )

    # Find unknown positions
    unknown_positions = [p for p in merged_portfolio.positions if p.ticker == "UNKNOWN"]

    # Should have 2 separate unknown positions
    assert len(unknown_positions) == 2

    # Verify first unknown position (from portfolio A)
    unknown1 = unknown_positions[0]
    assert unknown1.name == "Unknown Asset 1"
    assert unknown1.quantity == Decimal("2")
    assert unknown1.average_price == Decimal("100.00")
    assert unknown1.currency == Currency.USD

    # Verify second unknown position (from portfolio B)
    unknown2 = unknown_positions[1]
    assert unknown2.name == "Unknown Asset 2"
    assert unknown2.quantity == Decimal("1")
    assert unknown2.average_price == Decimal("200.00")
    assert unknown2.currency == Currency.USD


def test_portfolio_merger_case_insensitive_tickers(portfolio_merger):
    """Test that portfolio merger handles case-insensitive ticker matching."""
    portfolio1 = ImportedPortfolio(
        broker_name="Broker1",
        imported_at=datetime(2023, 1, 1, 12, 0, 0),
        positions=[
            StockPosition(
                # lowercase (will be converted to uppercase by validator)
                ticker="aapl",
                name="Apple Inc.",
                quantity=Decimal("10"),
                average_price=Decimal("150.00"),
                currency=Currency.USD,
            )
        ],
    )

    portfolio2 = ImportedPortfolio(
        broker_name="Broker2",
        imported_at=datetime(2023, 1, 1, 12, 0, 0),
        positions=[
            StockPosition(
                ticker="AAPL",  # uppercase
                name="Apple Inc.",
                quantity=Decimal("15"),
                average_price=Decimal("160.00"),
                currency=Currency.USD,
            )
        ],
    )

    merged_portfolio = portfolio_merger.merge_portfolios([portfolio1, portfolio2])

    # Should have merged the positions (case-insensitive)
    assert len(merged_portfolio.positions) == 1

    aapl_position = merged_portfolio.positions[0]
    assert (
        aapl_position.ticker == "AAPL"
    )  # Both are converted to uppercase by validator
    assert aapl_position.quantity == Decimal("25")
    assert aapl_position.average_price == Decimal("156.00")  # Weighted average


def test_portfolio_merger_different_currencies(portfolio_merger):
    """Test that portfolio merger preserves currency from first position."""
    portfolio1 = ImportedPortfolio(
        broker_name="Broker1",
        imported_at=datetime(2023, 1, 1, 12, 0, 0),
        positions=[
            StockPosition(
                ticker="AAPL",
                name="Apple Inc.",
                quantity=Decimal("10"),
                average_price=Decimal("150.00"),
                currency=Currency.USD,
            )
        ],
    )

    portfolio2 = ImportedPortfolio(
        broker_name="Broker2",
        imported_at=datetime(2023, 1, 1, 12, 0, 0),
        positions=[
            StockPosition(
                ticker="AAPL",
                name="Apple Inc.",
                quantity=Decimal("15"),
                average_price=Decimal("160.00"),
                currency=Currency.EUR,  # Different currency
            )
        ],
    )

    merged_portfolio = portfolio_merger.merge_portfolios([portfolio1, portfolio2])

    # Should have merged the positions, preserving first position's currency
    assert len(merged_portfolio.positions) == 1

    aapl_position = merged_portfolio.positions[0]
    assert aapl_position.ticker == "AAPL"
    assert aapl_position.quantity == Decimal("25")
    assert aapl_position.average_price == Decimal("156.00")
    assert aapl_position.currency == Currency.USD  # From first position


def test_portfolio_merger_weighted_average_calculation(portfolio_merger):
    """Test that portfolio merger calculates weighted average correctly."""
    portfolio1 = ImportedPortfolio(
        broker_name="Broker1",
        imported_at=datetime(2023, 1, 1, 12, 0, 0),
        positions=[
            StockPosition(
                ticker="AAPL",
                name="Apple Inc.",
                quantity=Decimal("100"),
                average_price=Decimal("100.00"),
                currency=Currency.USD,
            )
        ],
    )

    portfolio2 = ImportedPortfolio(
        broker_name="Broker2",
        imported_at=datetime(2023, 1, 1, 12, 0, 0),
        positions=[
            StockPosition(
                ticker="AAPL",
                name="Apple Inc.",
                quantity=Decimal("200"),
                average_price=Decimal("200.00"),
                currency=Currency.USD,
            )
        ],
    )

    merged_portfolio = portfolio_merger.merge_portfolios([portfolio1, portfolio2])

    aapl_position = merged_portfolio.positions[0]

    # Calculate expected weighted average:
    # Total value = (100 * 100) + (200 * 200) = 10,000 + 40,000 = 50,000
    # Total quantity = 100 + 200 = 300
    # Weighted average = 50,000 / 300 ≈ 166.666...
    expected_avg = Decimal("50000") / Decimal("300")

    assert aapl_position.quantity == Decimal("300")
    assert aapl_position.average_price == expected_avg


def test_portfolio_merger_multiple_unknown_positions(portfolio_merger):
    """Test that portfolio merger handles multiple unknown positions correctly."""
    portfolio1 = ImportedPortfolio(
        broker_name="Broker1",
        imported_at=datetime(2023, 1, 1, 12, 0, 0),
        positions=[
            StockPosition(
                ticker="UNKNOWN",
                name="Unknown 1",
                quantity=Decimal("1"),
                average_price=Decimal("100.00"),
                currency=Currency.USD,
            ),
            StockPosition(
                ticker="UNKNOWN",
                name="Unknown 2",
                quantity=Decimal("2"),
                average_price=Decimal("200.00"),
                currency=Currency.USD,
            ),
        ],
    )

    portfolio2 = ImportedPortfolio(
        broker_name="Broker2",
        imported_at=datetime(2023, 1, 1, 12, 0, 0),
        positions=[
            StockPosition(
                ticker="UNKNOWN",
                name="Unknown 3",
                quantity=Decimal("3"),
                average_price=Decimal("300.00"),
                currency=Currency.USD,
            )
        ],
    )

    merged_portfolio = portfolio_merger.merge_portfolios([portfolio1, portfolio2])

    # Should have 3 separate unknown positions
    unknown_positions = [p for p in merged_portfolio.positions if p.ticker == "UNKNOWN"]
    assert len(unknown_positions) == 3

    # Verify each unknown position is preserved
    assert unknown_positions[0].name == "Unknown 1"
    assert unknown_positions[0].quantity == Decimal("1")
    assert unknown_positions[0].average_price == Decimal("100.00")

    assert unknown_positions[1].name == "Unknown 2"
    assert unknown_positions[1].quantity == Decimal("2")
    assert unknown_positions[1].average_price == Decimal("200.00")

    assert unknown_positions[2].name == "Unknown 3"
    assert unknown_positions[2].quantity == Decimal("3")
    assert unknown_positions[2].average_price == Decimal("300.00")


def test_portfolio_weights_calculation(portfolio_merger):
    """Test that portfolio weights are calculated correctly."""
    portfolio = ImportedPortfolio(
        broker_name="TestBroker",
        imported_at=datetime(2023, 1, 1, 12, 0, 0),
        positions=[
            StockPosition(
                ticker="AAPL",
                name="Apple Inc.",
                quantity=Decimal("10"),
                average_price=Decimal("150.00"),
                currency=Currency.USD,
            ),
            StockPosition(
                ticker="MSFT",
                name="Microsoft Corp.",
                quantity=Decimal("5"),
                average_price=Decimal("300.00"),
                currency=Currency.USD,
            ),
        ],
    )

    # Calculate weights
    weighted_positions = portfolio_merger.calculate_portfolio_weights(portfolio)

    # Total portfolio value = (10 * 150) + (5 * 300) = 1500 + 1500 = 3000
    # AAPL weight = 1500 / 3000 = 0.5 (50%)
    # MSFT weight = 1500 / 3000 = 0.5 (50%)

    assert len(weighted_positions) == 2
    assert weighted_positions[0].ticker == "AAPL"
    assert weighted_positions[1].ticker == "MSFT"
