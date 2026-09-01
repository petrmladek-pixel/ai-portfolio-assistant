"""Ticker price model for caching current prices from Yahoo Finance."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlmodel import Column, Field, Numeric, SQLModel


class TickerPriceBase(SQLModel):
    """Base fields for ticker price caching."""

    ticker: str = Field(primary_key=True, index=True)
    price: Decimal = Field(
        sa_column=Column(Numeric(precision=18, scale=8, asdecimal=True))
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        nullable=False,
    )


class TickerPrice(TickerPriceBase, table=True, table_name="ticker_prices"):
    """Database model for caching Yahoo Finance ticker prices with 15-min TTL."""

    __tablename__ = "ticker_prices"
