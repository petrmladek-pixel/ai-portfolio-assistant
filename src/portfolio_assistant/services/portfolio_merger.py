"""Portfolio merger for combining multiple broker portfolios.

This module provides functionality to merge multiple portfolios by grouping
positions by ticker and calculating weighted average purchase prices.
"""

from decimal import Decimal

from portfolio_assistant.models.portfolio import (
    ImportedPortfolio,
    StockPosition,
)


class PortfolioMerger:
    """Portfolio merger for combining multiple broker portfolios.

    Groups positions by ticker (case-insensitive) and calculates weighted
    average purchase prices while preserving unknown assets separately.
    """

    @staticmethod
    def merge_portfolios(portfolios: list[ImportedPortfolio]) -> ImportedPortfolio:
        """Merge multiple portfolios into a single combined portfolio.

        Args:
            portfolios: List of ImportedPortfolio objects to merge.

        Returns:
            ImportedPortfolio: The merged portfolio with combined positions.

        Raises:
            ValueError: If no portfolios are provided.
        """
        if not portfolios:
            raise ValueError("No portfolios provided for merging")

        # Group positions by normalized ticker (case-insensitive)
        position_groups: dict[str, list[StockPosition]] = {}
        unknown_positions: list[StockPosition] = []

        for portfolio in portfolios:
            for position in portfolio.positions:
                normalized_ticker = position.ticker.upper()

                # Keep "UNKNOWN" positions separate
                if normalized_ticker == "UNKNOWN":
                    # Add unknown positions to separate list
                    unknown_positions.append(position)
                else:
                    # Group by normalized ticker
                    if normalized_ticker not in position_groups:
                        position_groups[normalized_ticker] = []

                    position_groups[normalized_ticker].append(position)

        # Merge positions within each group
        merged_positions: list[StockPosition] = []

        # Merge regular positions first (to preserve original order)
        for positions in position_groups.values():
            # Merge positions with the same ticker
            merged_position = PortfolioMerger._merge_positions(positions)
            merged_positions.append(merged_position)

        # Add unknown positions as-is (to preserve original order)
        merged_positions.extend(unknown_positions)

        # Create merged portfolio
        merged_portfolio = ImportedPortfolio(
            broker_name="MERGED",
            imported_at=portfolios[0].imported_at,  # Use first portfolio's timestamp
            positions=merged_positions,
        )

        return merged_portfolio

    @staticmethod
    def _merge_positions(positions: list[StockPosition]) -> StockPosition:
        """Merge multiple positions with the same ticker.

        Calculates:
        - Total quantity (sum of all quantities)
        - Total value (sum of quantity * average_price for each position)
        - Weighted average price (total_value / total_quantity)
        - Preserves the first position's name and currency

        Args:
            positions: List of StockPosition objects with the same ticker.

        Returns:
            StockPosition: The merged position with weighted average calculations.
        """
        if not positions:
            raise ValueError("No positions provided for merging")

        # Use first position as base
        base_position = positions[0]

        # Calculate total quantity and total value
        total_quantity = Decimal("0")
        total_value = Decimal("0")

        for position in positions:
            total_quantity += position.quantity
            total_value += position.quantity * position.average_price

        # Calculate weighted average price
        if total_quantity > 0:
            weighted_avg_price = total_value / total_quantity
        else:
            weighted_avg_price = Decimal("0")

        # Create merged position
        merged_position = StockPosition(
            ticker=base_position.ticker,
            name=base_position.name,
            quantity=total_quantity,
            average_price=weighted_avg_price,
            currency=base_position.currency,
        )

        return merged_position

    @staticmethod
    def calculate_portfolio_weights(
        portfolio: ImportedPortfolio,
    ) -> list[StockPosition]:
        """Calculate percentage weights for each position in a portfolio.

        Args:
            portfolio: The portfolio to calculate weights for.

        Returns:
            List[StockPosition]: Positions with updated weights.
        """
        if not portfolio.positions:
            return []

        # Calculate total portfolio value
        total_value = Decimal("0")
        for position in portfolio.positions:
            total_value += position.quantity * position.average_price

        # Calculate weights for each position
        weighted_positions: list[StockPosition] = []
        for position in portfolio.positions:
            position_value = position.quantity * position.average_price
            if total_value > 0:
                position.weight = position_value / total_value
            else:
                position.weight = Decimal("0")

            # Create new position with weight (note: StockPosition doesn't have
            # weight field)
            # For display purposes, we'll return the original positions
            weighted_positions.append(position)

        return weighted_positions
