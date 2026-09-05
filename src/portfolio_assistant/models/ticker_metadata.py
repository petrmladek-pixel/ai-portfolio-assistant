"""Ticker metadata model for caching sector and country information."""

from datetime import datetime

from sqlmodel import Field, SQLModel

from portfolio_assistant.core.types import UTCDateTime
from portfolio_assistant.core.utils import get_now_utc


class TickerMetadataBase(SQLModel):
    """Base fields for ticker metadata."""

    ticker: str = Field(primary_key=True, index=True)
    sector: str | None = Field(default="Unknown", index=True)
    country: str | None = Field(default="Unknown", index=True)
    updated_at: datetime = Field(
        default_factory=get_now_utc,
        nullable=False,
        sa_type=UTCDateTime,
    )


class TickerMetadata(TickerMetadataBase, table=True, table_name="ticker_metadata"):
    """Database model for caching Yahoo Finance ticker metadata."""

    __tablename__ = "ticker_metadata"
