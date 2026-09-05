"""Database-backed cache for current Yahoo Finance prices."""

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

import yfinance as yf
from sqlmodel import Session

from portfolio_assistant.core.utils import get_now_utc
from portfolio_assistant.crud.ticker_price import find_ticker_price, save_ticker_price

logger = logging.getLogger(__name__)

PRICE_CACHE_TTL = timedelta(minutes=15)


class PriceCacheService:
    """Retrieve and refresh cached current prices."""

    @staticmethod
    def get_current_prices(db: Session, tickers: list[str]) -> dict[str, Decimal]:
        """Return cached or freshly fetched prices for the supplied tickers."""
        prices: dict[str, Decimal] = {}
        for ticker in dict.fromkeys(ticker for ticker in tickers if ticker):
            cached = find_ticker_price(db, ticker)
            if cached is not None and _is_fresh(cached.updated_at):
                prices[ticker] = cached.price
                continue

            fetched_price = _fetch_price(ticker)
            if fetched_price is not None:
                save_ticker_price(db, ticker, fetched_price)
                prices[ticker] = fetched_price
            elif cached is not None:
                logger.warning("Using expired cached price for %s", ticker)
                prices[ticker] = cached.price
            else:
                logger.warning("No price is available for %s", ticker)
                prices[ticker] = Decimal("0.00")
        return prices


def _is_fresh(updated_at: datetime) -> bool:
    """Return whether a cache timestamp is within the price TTL."""
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    return get_now_utc() - updated_at < PRICE_CACHE_TTL


def _fetch_price(ticker: str) -> Decimal | None:
    """Fetch and validate a single current price from Yahoo Finance."""
    try:
        yahoo_ticker = yf.Ticker(ticker)
        price = yahoo_ticker.fast_info.get("lastPrice")
        if price is None:
            price = yahoo_ticker.info.get("currentPrice")
        if price is None:
            logger.warning("Yahoo Finance returned no price for %s", ticker)
            return None
        decimal_price = Decimal(str(price))
        if not decimal_price.is_finite() or decimal_price < 0:
            logger.warning("Yahoo Finance returned an invalid price for %s", ticker)
            return None
        return decimal_price
    except (InvalidOperation, TypeError, ValueError):
        logger.warning("Yahoo Finance returned an invalid price for %s", ticker)
    except Exception:
        logger.exception("Yahoo Finance price fetch failed for %s", ticker)
    return None
