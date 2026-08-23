"""Portfolio-related Pydantic models and enums.

This module contains models for representing portfolio stock positions and imported
portfolios using Pydantic V2 with strict validation and decimal financial values.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator
from pydantic.functional_validators import model_validator


class Currency(StrEnum):
    """Supported currencies for stock transactions and positions."""

    USD = "USD"
    EUR = "EUR"
    CZK = "CZK"
    GBP = "GBP"


class TransactionType(StrEnum):
    """Supported portfolio transaction types."""

    BUY = "BUY"
    SELL = "SELL"


class AnonymizedPosition(BaseModel):
    """Represents a privacy-preserving stock position with relative weight.

    Attributes:
    ticker (str): The stock ticker symbol (e.g., AAPL). Must be non-empty,
        1-15 characters, and contain only letters, numbers, dots, and hyphens.
        Automatically stripped of whitespace and converted to uppercase.
        name (str | None): The name of the company or stock.
        weight (Decimal): The percentage weight of this position in the portfolio.
            Must be strictly greater than 0 and less than or equal to 1.
        currency (Currency): The currency of the stock position.
    """

    ticker: str = Field(
        ..., min_length=1, max_length=15, pattern=r"^[A-Za-z0-9.\-]{1,15}$"
    )
    name: str | None = None
    weight: Decimal = Field(..., gt=0, le=1)
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
            ValueError: If the ticker is not a string or empty.
        """
        if not isinstance(v, str):
            raise ValueError("Ticker must be a string")
        cleaned = v.strip().upper()
        if not cleaned:
            raise ValueError("Ticker cannot be empty or only whitespace")
        return cleaned


class AnonymizedPortfolio(BaseModel):
    """Represents an anonymized portfolio with positions and their weights.

    Attributes:
        broker_name (str): The name of the importing broker.
        imported_at (datetime): The timestamp when the portfolio was imported.
        positions (list[AnonymizedPosition]): List of anonymized positions.
    """

    broker_name: str
    imported_at: datetime
    positions: list[AnonymizedPosition]


class StockPosition(BaseModel):
    """Represents a validated stock position in a portfolio.

    Attributes:
    ticker (str): The stock ticker symbol (e.g., AAPL). Must be non-empty,
        1-15 characters, and contain only letters, numbers, dots, and hyphens.
        Automatically stripped of whitespace and converted to uppercase.
        name (Optional[str]): The name of the company or stock.
        quantity (Decimal): The amount of stock owned. Must be strictly greater than 0.
        average_price (Decimal): The average purchase price. Must be strictly greater
        than 0.
        currency (Currency): The currency of the stock position.
    """

    ticker: str = Field(
        ..., min_length=1, max_length=15, pattern=r"^[A-Za-z0-9.\-]{1,15}$"
    )
    name: str | None = None
    quantity: Decimal
    average_price: Decimal
    currency: Currency
    weight: Decimal | None = Field(default=None, gt=0, le=1)

    @model_validator(mode="after")
    def validate_non_zero_for_active_positions(self) -> "StockPosition":
        """Ensures active positions have positive values, while allowing 0
        for UNKNOWN."""
        if self.ticker != "UNKNOWN":
            if self.quantity <= 0:
                raise ValueError(
                    "quantity must be strictly greater than 0 for active assets"
                )
            if self.average_price <= 0:
                raise ValueError(
                    "average_price must be strictly greater than 0 for active assets"
                )
        else:
            if self.quantity < 0:
                raise ValueError("quantity cannot be negative for UNKNOWN assets")
            if self.average_price < 0:
                raise ValueError("average_price cannot be negative for UNKNOWN assets")
        return self

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


class PortfolioCreate(BaseModel):
    """Represents the data required to create a new portfolio."""

    name: str = Field(..., min_length=1, max_length=100)
    broker: str = Field(..., min_length=1, max_length=50)

    @field_validator("name", "broker", mode="before")
    @classmethod
    def clean_string_fields(cls, v: str) -> str:
        """Strips whitespace from string fields."""
        if not isinstance(v, str):
            raise ValueError("Field must be a string")
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty or only whitespace")
        return cleaned


class ImportedPortfolio(BaseModel):
    """Represents an imported collection of stock positions from a broker.

    Attributes:
        broker_name (str): The name of the importing broker. Must be non-empty.
        imported_at (datetime): The timestamp when the portfolio was imported.
        positions (list[StockPosition]): List of validated stock positions.
    """

    broker_name: str = Field(..., min_length=1)
    imported_at: datetime
    positions: list[StockPosition] = Field(default_factory=list)

    def to_anonymized(self) -> AnonymizedPortfolio:
        """Converts the imported portfolio to an anonymized version with weights.

        Calculates weights based on the total value (quantity * average_price).
        Weights are calculated using decimal precision.

        Returns:
            AnonymizedPortfolio: The anonymized version of this portfolio.

        Raises:
            ValueError: If the portfolio is empty.
        """
        if not self.positions:
            return AnonymizedPortfolio(
                broker_name=self.broker_name,
                imported_at=self.imported_at,
                positions=[],
            )

        # Calculate position values and total portfolio value
        position_values = [
            (pos, pos.quantity * pos.average_price) for pos in self.positions
        ]
        total_value = sum((val for _, val in position_values), Decimal(0))

        anonymized_positions = []
        for pos, val in position_values:
            weight = val / total_value if total_value > 0 else Decimal(0)
            anonymized_positions.append(
                AnonymizedPosition(
                    ticker=pos.ticker,
                    name=pos.name,
                    weight=weight,
                    currency=pos.currency,
                )
            )

        return AnonymizedPortfolio(
            broker_name=self.broker_name,
            imported_at=self.imported_at,
            positions=anonymized_positions,
        )

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
