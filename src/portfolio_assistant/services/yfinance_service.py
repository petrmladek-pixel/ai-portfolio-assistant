"""Yahoo Finance metadata service for caching sector and country information."""

import logging
from datetime import UTC, timedelta
from decimal import Decimal
from time import perf_counter

import yfinance as yf
from sqlmodel import Session

from portfolio_assistant.core.utils import get_now_utc
from portfolio_assistant.crud.ticker_metadata import (
    get_ticker_metadata,
    save_ticker_metadata,
)
from portfolio_assistant.crud.ticker_price import (
    get_ticker_price,
    save_ticker_price,
)
from portfolio_assistant.models.ticker_metadata import TickerMetadata

logger = logging.getLogger(__name__)

# Cache TTL: 15 minutes for prices
PRICE_CACHE_TTL = timedelta(minutes=15)


class YFinanceService:
    """Service for fetching and caching ticker metadata from Yahoo Finance."""

    def __init__(self, db: Session) -> None:
        """Initialize the service with a database session.

        Args:
            db: SQLModel database session for caching metadata.
        """
        self.db = db

    def get_metadata(self, ticker: str) -> TickerMetadata:
        """Fetch ticker metadata with caching and 30-day expiration.

        Args:
            ticker: The ticker symbol to fetch metadata for.

        Returns:
            TickerMetadata: The cached or freshly fetched metadata record.
        """
        started_at = perf_counter()
        # Try to get cached metadata
        cached = get_ticker_metadata(self.db, ticker)

        if cached is not None:
            # Ensure updated_at is timezone-aware (SQLite may return naive datetime)
            updated_at = cached.updated_at
            if updated_at.tzinfo is None:
                # Assume naive datetime is UTC (as per our model default)
                updated_at = updated_at.replace(tzinfo=UTC)
                logger.info(
                    "[PROFILE] metadata cache timestamp for %s was naive; "
                    "normalized to UTC",
                    ticker,
                )

            # Check if cache is still valid (less than 30 days old)
            cache_expiry = timedelta(days=30)
            if get_now_utc() - updated_at < cache_expiry:
                logger.info(
                    "[PROFILE] get_metadata for %s took %.3fs (cache hit)",
                    ticker,
                    perf_counter() - started_at,
                )
                return cached

            logger.info("[PROFILE] metadata cache expired for %s", ticker)
        else:
            logger.info("[PROFILE] metadata cache miss for %s", ticker)

        # Cache miss or expired - fetch from Yahoo Finance
        sector = "Unknown"
        country = "Unknown"

        try:
            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.info

            # Extract sector and country, falling back to "Unknown"
            sector = info.get("sector", "Unknown") or "Unknown"
            country = info.get("country", "Unknown") or "Unknown"

            # Fix ETF classification based on quoteType
            quote_type = info.get("quoteType", "").upper()
            if quote_type in ("ETF", "MUTUALFUND"):
                sector = "ETF / Fund"
                country = "Global"

            # Ensure we have string values
            sector = str(sector) if sector else "Unknown"
            country = str(country) if country else "Unknown"
        except Exception:
            # On any error, use "Unknown" to prevent API slamming
            logger.exception("Yahoo Finance metadata fetch failed for %s", ticker)
            sector = "Unknown"
            country = "Unknown"

        # Save to cache (even on failure to protect the API)
        saved = save_ticker_metadata(self.db, ticker, sector, country)
        logger.info(
            "[PROFILE] get_metadata for %s took %.3fs (Yahoo Finance fetch)",
            ticker,
            perf_counter() - started_at,
        )
        return saved

    def get_current_price(self, ticker: str) -> Decimal:
        """Fetch the current price for a ticker with 15-minute caching.

        Args:
            ticker: The ticker symbol to fetch the price for.

        Returns:
            Decimal: The current price as a Decimal, or Decimal("0.00") on failure.
        """
        started_at = perf_counter()
        # Try to get cached price first
        cached = get_ticker_price(self.db, ticker)
        if cached is not None:
            logger.info(
                "[PROFILE] get_current_price for %s took %.3fs (cache hit)",
                ticker,
                perf_counter() - started_at,
            )
            return cached.price

        logger.info("[PROFILE] price cache miss or expired for %s", ticker)

        # Cache miss or expired - fetch from Yahoo Finance
        try:
            ticker_obj = yf.Ticker(ticker)
            # Try fast_info first (lighter weight)
            price = ticker_obj.fast_info.get("lastPrice")
            if price is None:
                # Fall back to info
                price = ticker_obj.info.get("currentPrice")

            if price is None:
                logger.warning(f"Could not fetch price for {ticker}: no price data")
                return Decimal("0.00")

            price_decimal = Decimal(str(price))
            # Save to cache
            save_ticker_price(self.db, ticker, price_decimal)
            logger.info(
                "[PROFILE] get_current_price for %s took %.3fs (Yahoo Finance fetch)",
                ticker,
                perf_counter() - started_at,
            )
            return price_decimal
        except Exception as e:
            logger.warning(f"Failed to fetch price for {ticker}: {e}")
            logger.info(
                "[PROFILE] get_current_price for %s took %.3fs (Yahoo Finance failure)",
                ticker,
                perf_counter() - started_at,
            )
            return Decimal("0.00")
