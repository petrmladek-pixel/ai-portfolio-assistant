"""Database operations for ticker price caching."""

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlmodel import Session, select

from portfolio_assistant.models.ticker_price import TickerPrice

# Cache TTL: 15 minutes
PRICE_CACHE_TTL = timedelta(minutes=15)
logger = logging.getLogger(__name__)


def get_ticker_price(db: Session, ticker: str) -> TickerPrice | None:
    """Return cached ticker price if it exists and is still valid (15 min TTL)."""
    statement = select(TickerPrice).where(TickerPrice.ticker == ticker)
    cached = db.exec(statement).first()

    if cached is None:
        return None

    # Ensure updated_at is timezone-aware (SQLite may return naive datetime)
    updated_at = cached.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
        logger.info(
            "[PROFILE] price cache timestamp for %s was naive; normalized to UTC",
            ticker,
        )

    # Check if cache is still valid (less than 15 minutes old)
    if datetime.now(UTC) - updated_at < PRICE_CACHE_TTL:
        return cached

    logger.info("[PROFILE] price cache expired for %s", ticker)

    return None


def save_ticker_price(db: Session, ticker: str, price: Decimal) -> TickerPrice:
    """Save or update ticker price with upsert logic."""
    current_time = datetime.now(UTC)

    # Query for existing record regardless of TTL - we want to update existing records
    statement = select(TickerPrice).where(TickerPrice.ticker == ticker)
    metadata = db.exec(statement).first()

    if metadata:
        metadata.price = price
        metadata.updated_at = current_time
        db.add(metadata)
    else:
        metadata = TickerPrice(
            ticker=ticker,
            price=price,
            updated_at=current_time,
        )
        db.add(metadata)

    db.commit()
    db.refresh(metadata)
    return metadata


def get_ticker_prices(db: Session, tickers: list[str]) -> dict[str, Decimal]:
    """Get cached prices for multiple tickers that are still valid."""
    prices = {}
    current_time = datetime.now(UTC)

    for ticker in tickers:
        statement = select(TickerPrice).where(TickerPrice.ticker == ticker)
        cached = db.exec(statement).first()

        if cached is not None:
            updated_at = cached.updated_at
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=UTC)
                logger.info(
                    "[PROFILE] price cache timestamp for %s was naive; "
                    "normalized to UTC",
                    ticker,
                )

            if current_time - updated_at < PRICE_CACHE_TTL:
                prices[ticker] = cached.price

    return prices


def save_ticker_prices(db: Session, prices: dict[str, Decimal]) -> list[TickerPrice]:
    """Save or update multiple ticker prices with upsert logic."""
    current_time = datetime.now(UTC)
    saved_prices = []

    for ticker, price in prices.items():
        # Query for existing record regardless of TTL - update existing records
        statement = select(TickerPrice).where(TickerPrice.ticker == ticker)
        existing = db.exec(statement).first()

        if existing:
            existing.price = price
            existing.updated_at = current_time
            db.add(existing)
            saved_prices.append(existing)
        else:
            new_price = TickerPrice(
                ticker=ticker,
                price=price,
                updated_at=current_time,
            )
            db.add(new_price)
            saved_prices.append(new_price)

    db.commit()
    for saved in saved_prices:
        db.refresh(saved)

    return saved_prices
