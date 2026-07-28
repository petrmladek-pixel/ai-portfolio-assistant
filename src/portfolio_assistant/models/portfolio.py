"""Portfolio-related Pydantic models and enums.

This module contains models for representing portfolio stock positions and imported
portfolios using Pydantic V2 with strict validation and decimal financial values.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class Currency(StrEnum):
    """Supported currencies for stock transactions and positions."""

    USD = "USD"
    EUR = "EUR"
    CZK = "CZK"


class TransactionType(StrEnum):
    """Supported portfolio transaction types."""

    BUY = "BUY"
    SELL = "SELL"


class StockPosition(BaseModel):
    """Represents a validated stock position in a portfolio.

    Attributes:
        ticker (str): The stock ticker symbol (e.g., AAPL). Must be non-empty.
            Automatically stripped of whitespace and converted to uppercase.
        name (Optional[str]): The name of the company or stock.
        quantity (Decimal): The amount of stock owned. Must be strictly greater than 0.
        average_price (Decimal): The average purchase price. Must be strictly greater 
        than 0.
        currency (Currency): The currency of the stock position.
    """

    ticker: str = Field(..., min_length=1)
    name: str | None = None
    quantity: Decimal = Field(..., gt=0)
    average_price: Decimal = Field(..., gt=0)
    currency: Currency

    @field_validator("ticker", mode="before")
    @classmethod
    def clean_ticker(cls, v: str) -> str:
        """Strips whitespace and converts the ticker to uppercase.

        Args:
            v (str): The raw ticker value.

        Returns:
            str: The cleaned and uppercase ticker.

        Raises:
            ValueError: If the ticker is not a string.
        """
        if not isinstance(v, str):
            raise ValueError("Ticker must be a string")
        cleaned = v.strip().upper()
        if not cleaned:
            raise ValueError("Ticker cannot be empty or only whitespace")
        return cleaned


class ImportedPortfolio(BaseModel):
    """Represents an imported collection of stock positions from a broker.

    Attributes:
        broker_name (str): The name of the importing broker. Must be non-empty.
        imported_at (datetime): The timestamp when the portfolio was imported.
        positions (List[StockPosition]): List of validated stock positions.
    """

    broker_name: str = Field(..., min_length=1)
    imported_at: datetime
    positions: list[StockPosition] = Field(default_factory=list)

    @field_validator("broker_name", mode="before")
    @classmethod
    def clean_broker_name(cls, v: str) -> str:
        """Validates that broker name is not empty or whitespace.

        Args:
            v (str): The raw broker name.

        Returns:
            str: The cleaned broker name.

        Raises:
            ValueError: If the broker name is not a string or empty.
        """
        if not isinstance(v, str):
            raise ValueError("Broker name must be a string")
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Broker name cannot be empty or only whitespace")
        return cleaned
