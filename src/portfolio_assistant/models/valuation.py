"""Pydantic models for portfolio valuation.

This module contains models for representing valued portfolio positions and
portfolios after current market prices and exchange rates are applied.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from portfolio_assistant.models.portfolio import (
    AnonymizedPortfolio,
    AnonymizedPosition,
    Currency,
)


class ValuedPosition(BaseModel):
    """Represents a valued stock position in a target currency.

    Attributes:
        ticker (str): The stock ticker symbol.
        name (str | None): The name of the company or stock.
        quantity (Decimal): The amount of stock owned.
        unit_price_original (Decimal): Current price in original currency.
        currency_original (Currency): The original currency of the stock.
        unit_price_target (Decimal): Current price in target currency.
        currency_target (Currency): The target currency for valuation.
        total_value_target (Decimal): Total value (quantity * unit_price_target).
        weight (Decimal): Weight of this position in the valued portfolio (0 to 1).
    """

    ticker: str = Field(..., min_length=1)
    name: str | None = None
    quantity: Decimal = Field(..., gt=0)
    unit_price_original: Decimal = Field(..., gt=0)
    currency_original: Currency
    unit_price_target: Decimal = Field(..., gt=0)
    currency_target: Currency
    total_value_target: Decimal = Field(..., gt=0)
    weight: Decimal = Field(..., ge=0, le=1)


class ValuedPortfolio(BaseModel):
    """Represents a portfolio with current market valuations.

    Attributes:
        broker_name (str): The name of the importing broker.
        imported_at (datetime): The timestamp when the portfolio was imported.
        valued_at (datetime): The timestamp when the valuation was performed.
        positions (list[ValuedPosition]): List of valued positions.
        total_value (Decimal): Total value of the portfolio in target currency.
        target_currency (Currency): The currency used for valuation.
    """

    broker_name: str = Field(..., min_length=1)
    imported_at: datetime
    valued_at: datetime
    positions: list[ValuedPosition] = Field(default_factory=list)
    total_value: Decimal = Field(..., ge=0)
    target_currency: Currency

    def to_anonymized(self) -> AnonymizedPortfolio:
        """Converts the valued portfolio to an AnonymizedPortfolio.

        The weights are based on current market values instead of historical
        average costs.

        Returns:
            AnonymizedPortfolio: The anonymized version of the valued portfolio.
        """
        anonymized_positions = [
            AnonymizedPosition(
                ticker=pos.ticker,
                name=pos.name,
                weight=pos.weight,
                currency=pos.currency_original,
            )
            for pos in self.positions
        ]

        return AnonymizedPortfolio(
            broker_name=self.broker_name,
            imported_at=self.imported_at,
            positions=anonymized_positions,
        )
