"""Portfolio aggregation service for calculating sector and country allocations."""

import logging
from decimal import Decimal
from typing import Any

from sqlmodel import Session, select

from portfolio_assistant.models.db_models import Portfolio, Position
from portfolio_assistant.services.yfinance_service import YFinanceService

logger = logging.getLogger(__name__)


class PortfolioAggregationService:
    """Service for calculating portfolio allocations by sector and country."""

    def __init__(self, db: Session) -> None:
        """Initialize the service with a database session.

        Args:
            db: SQLModel database session.
        """
        self.db = db
        self.yfinance = YFinanceService(db)

    def get_portfolio_allocation(self, portfolio_id: int) -> dict[str, Any]:
        """Calculate sector and country allocation for a portfolio.

        Args:
            portfolio_id: The ID of the portfolio to analyze.

        Returns:
            dict[str, Any]: Dictionary with sectors and countries allocation data
                in a format suitable for Chart.js.
        """
        # Fetch portfolio and positions
        portfolio = self.db.exec(
            select(Portfolio).where(Portfolio.id == portfolio_id)
        ).first()

        if portfolio is None:
            logger.warning(f"Portfolio {portfolio_id} not found")
            return {
                "sectors": {"labels": [], "data": []},
                "countries": {"labels": [], "data": []},
            }

        positions = self.db.exec(
            select(Position).where(Position.portfolio_id == portfolio_id)
        ).all()

        if not positions:
            logger.warning(f"Portfolio {portfolio_id} has no positions")
            return {
                "sectors": {"labels": [], "data": []},
                "countries": {"labels": [], "data": []},
            }

        # Track allocations
        sector_totals: dict[str, Decimal] = {}
        country_totals: dict[str, Decimal] = {}
        total_value: Decimal = Decimal("0.00")

        # Calculate values and metadata for all positions first
        position_data = []
        for pos in positions:
            if pos.ticker == "CASH":
                # Cash position: value is quantity * unit_cost
                value = pos.quantity * pos.unit_cost
                sector = "Cash"
                country = "Cash"
            else:
                # Fetch current price (uses caching from YFinanceService)
                price = self.yfinance.get_current_price(pos.ticker)
                value = pos.quantity * price

                # Fetch metadata for sector and country
                metadata = self.yfinance.get_metadata(pos.ticker)
                sector = metadata.sector or "Unknown"
                country = metadata.country or "Unknown"

            position_data.append((pos, value, sector, country))

        # Sort positions by value descending for consistent ordering
        position_data.sort(key=lambda x: x[1], reverse=True)

        # Process sorted positions
        for _, value, sector, country in position_data:
            # Add to sector total
            sector_totals[sector] = sector_totals.get(sector, Decimal("0.00")) + value

            # Add to country total
            country_totals[country] = (
                country_totals.get(country, Decimal("0.00")) + value
            )

            total_value += value

        # Handle zero total value
        if total_value == Decimal("0.00"):
            logger.warning(f"Portfolio {portfolio_id} has zero total value")
            return {
                "sectors": {"labels": [], "data": []},
                "countries": {"labels": [], "data": []},
            }

        # Convert to percentages rounded to 2 decimal places
        def to_percentages(totals: dict[str, Decimal]) -> dict[str, Any]:
            """Convert value totals to percentages of total portfolio value."""
            sorted_items = sorted(totals.items(), key=lambda x: x[1], reverse=True)
            labels = []
            data = []
            for label, value in sorted_items:
                percentage = round((value / total_value) * Decimal("100"), 2)
                labels.append(label)
                data.append(float(percentage))
            return {"labels": labels, "data": data}

        return {
            "sectors": to_percentages(sector_totals),
            "countries": to_percentages(country_totals),
        }
