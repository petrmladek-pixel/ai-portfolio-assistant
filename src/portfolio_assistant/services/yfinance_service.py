"""Compatibility facade for focused Yahoo Finance cache services."""

from decimal import Decimal

import yfinance as yf  # noqa: F401
from sqlmodel import Session

from portfolio_assistant.crud.ticker_metadata import get_ticker_metadata
from portfolio_assistant.models.ticker_metadata import TickerMetadata
from portfolio_assistant.services.metadata_cache import MetadataCacheService
from portfolio_assistant.services.price_cache import PriceCacheService


class YFinanceService:
    """Provide the deprecated single-ticker Yahoo Finance API."""

    def __init__(self, db: Session) -> None:
        """Initialize the compatibility facade with a database session."""
        self.db = db

    def get_metadata(self, ticker: str) -> TickerMetadata:
        """Return metadata through :class:`MetadataCacheService`."""
        MetadataCacheService.get_tickers_metadata(self.db, [ticker])
        metadata = get_ticker_metadata(self.db, ticker)
        if metadata is None:
            raise RuntimeError("Metadata cache was not populated")
        return metadata

    def get_current_price(self, ticker: str) -> Decimal:
        """Return a price through :class:`PriceCacheService`."""
        return PriceCacheService.get_current_prices(self.db, [ticker])[ticker]
