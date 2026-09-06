"""Allocation calculation service for portfolio management.

This module provides stateless calculation logic for determining portfolio
asset allocations based on current positions and market prices.
"""

from collections.abc import Sequence
from decimal import Decimal
from typing import TypedDict

from sqlmodel import Session, select

from portfolio_assistant.models.allocation import (
    AssetAllocation,
    PortfolioAllocationResponse,
)
from portfolio_assistant.models.db_models import Portfolio, Position
from portfolio_assistant.services.market_data.yfinance import (
    YFinanceMarketDataService,
)
from portfolio_assistant.services.metadata_cache import MetadataCacheService
from portfolio_assistant.services.price_cache import PriceCacheService


class _AllocationDraft(TypedDict):
    """Intermediate allocation values before percentage calculation."""

    ticker: str
    quantity: Decimal
    current_price: Decimal
    market_value: Decimal


class AllocationService:
    """Service for calculating portfolio allocations from current positions."""

    async def calculate_portfolio_allocations(
        self,
        session: Session,
        portfolio_id: int | None = None,
        user_id: int | None = None,
    ) -> PortfolioAllocationResponse:
        """Calculate asset allocations for a portfolio.

        Args:
            session (Session): The database session.
            portfolio_id (int | None): The ID of the portfolio to analyze, or
                None to analyze all portfolios.
            user_id (int | None): Restrict an all-portfolios analysis to a user.
        Returns:
            PortfolioAllocationResponse: The calculated allocation data.
        """
        if portfolio_id is None:
            if user_id is None:
                positions = session.exec(select(Position)).all()
            else:
                positions = session.exec(
                    select(Position).join(Portfolio).where(Portfolio.user_id == user_id)
                ).all()
        else:
            positions = session.exec(
                select(Position).where(Position.portfolio_id == portfolio_id)
            ).all()
        tickers = list({pos.ticker for pos in positions if pos.ticker != "CASH"})
        prices = PriceCacheService.get_current_prices(session, tickers)
        exchange_rates = await self._get_exchange_rates(session, positions)
        metadata_by_ticker = MetadataCacheService.get_tickers_metadata(session, tickers)

        allocations: list[_AllocationDraft] = []
        total_value = Decimal("0.00")
        for position in positions:
            if position.ticker == "CASH":
                current_price = position.unit_cost
                market_value = position.quantity * position.unit_cost
            else:
                current_price = prices[position.ticker]
                market_value = (
                    position.quantity
                    * current_price
                    * exchange_rates[position.currency]
                )
            allocations.append(
                {
                    "ticker": position.ticker,
                    "quantity": position.quantity,
                    "current_price": current_price,
                    "market_value": market_value,
                }
            )
            total_value += market_value

        if total_value == 0:
            return PortfolioAllocationResponse(
                portfolio_id=portfolio_id,
                total_value=Decimal("0.00"),
                allocations=[],
            )

        final_allocations: list[AssetAllocation] = []
        for alloc in allocations:
            percentage = (alloc["market_value"] / total_value) * 100
            if alloc["ticker"] == "CASH":
                sector = "Cash"
                region = "Cash"
            else:
                metadata = metadata_by_ticker.get(alloc["ticker"], {})
                sector = str(metadata.get("sector") or "Unknown")
                region = str(metadata.get("country") or "Unknown")
            final_allocations.append(
                AssetAllocation(
                    ticker=alloc["ticker"],
                    quantity=alloc["quantity"],
                    current_price=alloc["current_price"],
                    market_value=alloc["market_value"],
                    percentage=percentage,
                    sector=sector,
                    region=region,
                )
            )

        return PortfolioAllocationResponse(
            portfolio_id=portfolio_id,
            total_value=total_value,
            allocations=final_allocations,
        )

    @staticmethod
    async def _get_exchange_rates(
        session: Session,
        positions: Sequence[Position],
    ) -> dict[str, Decimal]:
        """Return exchange rates for converting position values to CZK."""
        currencies = {
            position.currency
            for position in positions
            if position.ticker != "CASH" and position.currency != "CZK"
        }
        exchange_rates = {"CZK": Decimal("1")}
        market_data = YFinanceMarketDataService(db_session=session)
        for currency in currencies:
            exchange_rates[currency] = await market_data.get_exchange_rate(
                currency, "CZK"
            )
        return exchange_rates
