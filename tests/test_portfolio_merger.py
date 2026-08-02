from datetime import datetime
from decimal import Decimal

from portfolio_assistant.models.portfolio import (
    Currency,
    ImportedPortfolio,
    StockPosition,
)
from portfolio_assistant.services.portfolio_merger import PortfolioMerger


def test_portfolio_merger_basic():
    merger = PortfolioMerger()

    p1 = ImportedPortfolio(
        broker_name="Broker 1",
        imported_at=datetime.now(),
        positions=[
            StockPosition(
                ticker="AAPL",
                name="Apple",
                quantity=Decimal("10"),
                average_price=Decimal("150"),
                currency=Currency.CZK,
            ),
            StockPosition(
                ticker="MSFT",
                name="Microsoft",
                quantity=Decimal("5"),
                average_price=Decimal("300"),
                currency=Currency.CZK,
            ),
        ],
    )

    p2 = ImportedPortfolio(
        broker_name="Broker 2",
        imported_at=datetime.now(),
        positions=[
            StockPosition(
                ticker="AAPL",
                name="Apple Inc.",
                quantity=Decimal("5"),
                average_price=Decimal("160"),
                currency=Currency.CZK,
            ),
        ],
    )

    merged = merger.merge_portfolios([p1, p2])

    assert len(merged) == 2

    aapl = next(p for p in merged if p.ticker == "AAPL")
    assert aapl.quantity == Decimal("15")
    # (10*150 + 5*160) / 15 = (1500 + 800) / 15 = 2300 / 15 = 153.333...
    assert aapl.average_price_czk == Decimal("2300") / Decimal("15")
    assert aapl.total_value_czk == Decimal("2300")

    msft = next(p for p in merged if p.ticker == "MSFT")
    assert msft.quantity == Decimal("5")
    assert msft.average_price_czk == Decimal("300")
    assert msft.total_value_czk == Decimal("1500")

    # Total value = 2300 + 1500 = 3800
    assert aapl.weight == Decimal("2300") / Decimal("3800")
    assert msft.weight == Decimal("1500") / Decimal("3800")
