"""Portfolio aggregation service for calculating sector and country allocations."""

import logging
from decimal import Decimal
from time import perf_counter
from typing import Any

from sqlmodel import Session, select

from portfolio_assistant.models.db_models import Portfolio, Position
from portfolio_assistant.services.metadata_cache import MetadataCacheService
from portfolio_assistant.services.price_cache import PriceCacheService

logger = logging.getLogger(__name__)


class PortfolioAggregationService:
    """Service for calculating portfolio allocations by sector and country."""

    def __init__(self, db: Session) -> None:
        """Initialize the service with a database session.

        Args:
            db: SQLModel database session.
        """
        self.db = db

    def get_portfolio_allocation(self, portfolio_id: int) -> dict[str, Any]:
        """Calculate sector and country allocation for a portfolio.

        Args:
            portfolio_id: The ID of the portfolio to analyze.

        Returns:
            dict[str, Any]: Dictionary with sectors and countries allocation data
                in a format suitable for Chart.js.
        """
        started_at = perf_counter()
        # Fetch portfolio and positions
        query_started_at = perf_counter()
        portfolio = self.db.exec(
            select(Portfolio).where(Portfolio.id == portfolio_id)
        ).first()
        logger.info(
            "[PROFILE] portfolio query for %s took %.3fs",
            portfolio_id,
            perf_counter() - query_started_at,
        )

        if portfolio is None:
            logger.warning(f"Portfolio {portfolio_id} not found")
            return {
                "sectors": {"labels": [], "data": []},
                "countries": {"labels": [], "data": []},
            }

        query_started_at = perf_counter()
        positions = self.db.exec(
            select(Position).where(Position.portfolio_id == portfolio_id)
        ).all()
        logger.info(
            "[PROFILE] positions query for %s took %.3fs (%d rows)",
            portfolio_id,
            perf_counter() - query_started_at,
            len(positions),
        )

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

        tickers = list({pos.ticker for pos in positions if pos.ticker != "CASH"})
        prices = PriceCacheService.get_current_prices(self.db, tickers)
        metadata_by_ticker = MetadataCacheService.get_tickers_metadata(self.db, tickers)

        # Calculate values and metadata for all positions first
        loop_started_at = perf_counter()
        position_data = []
        for pos in positions:
            if pos.ticker == "CASH":
                # Cash position: value is quantity * unit_cost
                value = pos.quantity * pos.unit_cost
                sector = "Cash"
                country = "Cash"
            else:
                price = prices[pos.ticker]
                value = pos.quantity * price

                metadata = metadata_by_ticker[pos.ticker]
                sector = str(metadata["sector"])
                country = str(metadata["country"])

            position_data.append((pos, value, sector, country))

        logger.info(
            "[PROFILE] allocation loop for %s took %.3fs (%d positions)",
            portfolio_id,
            perf_counter() - loop_started_at,
            len(positions),
        )

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

        allocation = {
            "sectors": to_percentages(sector_totals),
            "countries": to_percentages(country_totals),
        }
        logger.info(
            "[PROFILE] get_portfolio_allocation for %s took %.3fs",
            portfolio_id,
            perf_counter() - started_at,
        )
        return allocation
