"""Pydantic models for portfolio allocation responses.

This module contains models for representing portfolio asset allocations
and their calculated percentages using Pydantic V2 with decimal precision.
"""

from decimal import Decimal

from pydantic import BaseModel


class AssetAllocation(BaseModel):
    """Represents a single asset holding with its calculated allocation data.

    Attributes:
        ticker (str): The stock ticker symbol (e.g., AAPL).
        quantity (Decimal): The net quantity held for this asset.
        current_price (Decimal): The current market price per unit.
        market_value (Decimal): The total market value (quantity *
            current_price).
        percentage (Decimal): The percentage share of this asset in the portfolio.
    """

    ticker: str
    quantity: Decimal
    current_price: Decimal
    market_value: Decimal
    percentage: Decimal


class PortfolioAllocationResponse(BaseModel):
    """Represents the complete allocation breakdown for a portfolio.

    Attributes:
        portfolio_id (int): The ID of the portfolio being analyzed.
        total_value (Decimal): The total market value of all assets in the portfolio.
        allocations (list[AssetAllocation]): List of individual asset allocations.
    """

    portfolio_id: int
    total_value: Decimal
    allocations: list[AssetAllocation]
