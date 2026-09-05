"""Database-backed cache for Yahoo Finance ticker metadata."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import yfinance as yf
from sqlmodel import Session

from portfolio_assistant.core.utils import get_now_utc
from portfolio_assistant.crud.ticker_metadata import (
    get_ticker_metadata,
    save_ticker_metadata,
)

logger = logging.getLogger(__name__)

METADATA_CACHE_TTL = timedelta(days=30)


class MetadataCacheService:
    """Retrieve and refresh cached sector and country metadata."""

    @staticmethod
    def get_tickers_metadata(
        db: Session, tickers: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Return cached or freshly fetched metadata for supplied tickers."""
        metadata_by_ticker: dict[str, dict[str, Any]] = {}
        for ticker in dict.fromkeys(ticker for ticker in tickers if ticker):
            cached = get_ticker_metadata(db, ticker)
            if cached is not None and _is_fresh(cached.updated_at):
                metadata_by_ticker[ticker] = _as_dict(cached.sector, cached.country)
                continue

            fetched = _fetch_metadata(ticker)
            if fetched is None and cached is not None:
                logger.warning("Using expired cached metadata for %s", ticker)
                metadata_by_ticker[ticker] = _as_dict(cached.sector, cached.country)
                continue

            sector, country = fetched or ("Unknown", "Unknown")
            saved = save_ticker_metadata(db, ticker, sector, country)
            metadata_by_ticker[ticker] = _as_dict(saved.sector, saved.country)
        return metadata_by_ticker


def _is_fresh(updated_at: datetime) -> bool:
    """Return whether a cache timestamp is within the metadata TTL."""
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    return get_now_utc() - updated_at < METADATA_CACHE_TTL


def _fetch_metadata(ticker: str) -> tuple[str, str] | None:
    """Fetch sector and country metadata from Yahoo Finance."""
    try:
        info = yf.Ticker(ticker).info
        sector = str(info.get("sector") or "Unknown")
        country = str(info.get("country") or "Unknown")
        if str(info.get("quoteType") or "").upper() in {"ETF", "MUTUALFUND"}:
            return "ETF / Fund", "Global"
        return sector, country
    except Exception:
        logger.exception("Yahoo Finance metadata fetch failed for %s", ticker)
        return None


def _as_dict(sector: str | None, country: str | None) -> dict[str, Any]:
    """Build the public metadata shape from a cached database record."""
    return {
        "sector": sector or "Unknown",
        "country": country or "Unknown",
    }
