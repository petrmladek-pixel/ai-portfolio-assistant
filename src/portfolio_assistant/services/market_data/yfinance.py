"""Yahoo Finance market data service implementation.

This module provides a concrete implementation of the BaseMarketDataService
using the yfinance library to fetch current prices and exchange rates.
"""

import asyncio
import logging
from datetime import timedelta
from decimal import ConversionSyntax, Decimal
from time import perf_counter
from typing import Any

import pandas as pd
import yfinance as yf

from portfolio_assistant.services.isin_resolver import YahooISINResolver
from portfolio_assistant.services.market_data.base import BaseMarketDataService

logger = logging.getLogger(__name__)

# Cache TTL: 15 minutes for prices
PRICE_CACHE_TTL = timedelta(minutes=15)


def _get_ticker_prices(db: Any, tickers: list[str]) -> dict[str, Decimal]:
    """Get cached prices for multiple tickers."""
    try:
        from portfolio_assistant.crud.ticker_price import get_ticker_prices

        return get_ticker_prices(db, tickers)
    except ImportError:
        return {}


def _save_ticker_prices(db: Any, prices: dict[str, Decimal]) -> None:
    """Save prices to cache."""
    try:
        from portfolio_assistant.crud.ticker_price import save_ticker_prices

        save_ticker_prices(db, prices)
    except ImportError:
        pass


class YFinanceMarketDataService(BaseMarketDataService):
    """Market data service using Yahoo Finance with optional caching."""

    def __init__(
        self, isin_resolver: YahooISINResolver | None = None, db_session: Any = None
    ) -> None:
        """Initialize the base parser with an optional ISIN resolver and DB session.

        Args:
            isin_resolver: Optional YahooISINResolver instance.
            db_session: Optional SQLModel database session for caching.
        """
        self.isin_resolver = isin_resolver or YahooISINResolver()
        self.db_session = db_session

    def _get_currency(self, ticker: str) -> str:
        """Helper to fetch the currency of a ticker using yfinance's fast_info."""
        try:
            import yfinance as yf

            return str(yf.Ticker(ticker).fast_info.get("currency", ""))
        except Exception:
            return ""

    async def get_current_prices(
        self, tickers: list[str], db_session: Any = None
    ) -> dict[str, Decimal]:
        """Fetch current market prices for a list of tickers asynchronously.

        Uses cached prices if available (15-minute TTL) to avoid redundant API calls.

        Args:
            tickers (list[str]): A list of ticker symbols or ISINs.
            db_session (Any, optional): Database session for caching. If provided,
                overrides the instance session.

        Returns:
            dict[str, Decimal]: A dictionary mapping each ticker (uppercase)
                to its current price as a Decimal.
        """
        if not tickers:
            return {}

        started_at = perf_counter()
        import re

        tickers_upper = [t.upper() for t in tickers]

        # Try to get cached prices first if we have a database session
        # Use the provided session or fall back to the instance session
        session_to_use = db_session if db_session is not None else self.db_session
        cached_prices: dict[str, Decimal] = {}
        if session_to_use is not None:
            cached_prices = _get_ticker_prices(session_to_use, tickers_upper)
            logger.debug(f"Found {len(cached_prices)} cached prices")

        # Identify which tickers still need fetching
        tickers_to_fetch = [t for t in tickers_upper if t not in cached_prices]

        if not tickers_to_fetch:
            # All prices were cached
            logger.info(
                "[PROFILE] get_current_prices for %d tickers took %.3fs "
                "(all cache hits)",
                len(tickers_upper),
                perf_counter() - started_at,
            )
            return cached_prices

        resolved_tickers: list[str] = []
        ticker_map: dict[str, str] = {}

        # 1. Asynchronously resolve all ISINs before downloading
        for t in tickers_to_fetch:
            if re.match(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$", t):
                resolved = await self.isin_resolver.resolve_isin(t)
                if resolved:
                    resolved_tickers.append(resolved)
                    ticker_map[resolved] = t
                else:
                    logger.warning(f"Skipping price fetch for unresolved ISIN: {t}")
            else:
                resolved_tickers.append(t)
                ticker_map[t] = t

        if not resolved_tickers:
            msg = (
                f"Could not fetch prices for tickers: "
                f"{', '.join(sorted(tickers_to_fetch))}"
            )
            logger.warning(msg)
            raise ValueError(msg)

        # 2. yf.download performs synchronous network I/O; wrap in asyncio.to_thread
        df = await asyncio.to_thread(
            yf.download,
            resolved_tickers,
            period="1d",
            progress=False,
        )

        fetched_prices: dict[str, Decimal] = {}
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            tickers_str = ", ".join(sorted(tickers_to_fetch))
            msg = f"Could not fetch prices for tickers: {tickers_str}"
            logger.warning(msg)
            raise ValueError(msg)

        # 3. Extract close prices and apply case-sensitive currency corrections
        for resolved_ticker in resolved_tickers:
            try:
                price = self._extract_close_price(df, resolved_ticker)

                # Check for London Pence vs Pound issue (GBp/GBX vs GBP/USD/EUR)
                if resolved_ticker.upper().endswith(".L"):
                    # Fetch currency using yfinance's lightweight fast_info API
                    currency = await asyncio.to_thread(
                        self._get_currency, resolved_ticker
                    )
                    if currency in ["GBp", "GBX"]:
                        price = price / Decimal("100.00")
                        logger.debug(
                            f"Converted London Stock Exchange (.L) "
                            f"ticker '{resolved_ticker}' "
                            f"price from Pence to Pounds: {price * 100} -> {price}"
                        )

                original_key = ticker_map[resolved_ticker]
                fetched_prices[original_key] = price
            except ValueError:
                original_key = ticker_map.get(resolved_ticker, resolved_ticker)
                logger.warning(f"Could not fetch price for ticker: {original_key}")
                continue

        # 4. Check for missing tickers based on the original queried keys
        missing = set(tickers_to_fetch) - set(fetched_prices.keys())
        if missing:
            msg = f"Could not fetch prices for tickers: {', '.join(sorted(missing))}"
            logger.warning(msg)
            raise ValueError(msg)

        # Cache the fetched prices if we have a database session
        if session_to_use is not None and fetched_prices:
            _save_ticker_prices(session_to_use, fetched_prices)
            logger.debug(f"Cached {len(fetched_prices)} new prices")

        # Combine cached and fetched prices
        result = {**cached_prices, **fetched_prices}
        logger.info(
            "[PROFILE] get_current_prices for %d tickers took %.3fs "
            "(%d cache hits, %d Yahoo Finance fetches)",
            len(tickers_upper),
            perf_counter() - started_at,
            len(cached_prices),
            len(tickers_to_fetch),
        )
        return result

    async def get_exchange_rate(self, from_currency: str, to_currency: str) -> Decimal:
        """Fetch currency exchange rate between two currencies asynchronously.

        If from_currency and to_currency are the same, returns Decimal("1.0")
        without making any network call.

        Args:
            from_currency (str): The currency to convert from (e.g., USD).
            to_currency (str): The currency to convert to (e.g., CZK).

        Returns:
            Decimal: The exchange rate as a Decimal.

        Raises:
            ValueError: If the exchange rate could not be fetched.
        """
        from_curr = from_currency.upper()
        to_curr = to_currency.upper()

        if from_curr == to_curr:
            return Decimal("1.0")

        ticker = f"{from_curr}{to_curr}=X"

        # yf.download performs synchronous network I/O; wrap in asyncio.to_thread
        df = await asyncio.to_thread(
            yf.download,
            ticker,
            period="1d",
            progress=False,
        )

        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError(
                f"Could not fetch exchange rate for {from_curr} to {to_curr}"
            )

        try:
            return self._extract_close_price(df, ticker)
        except ValueError as e:
            raise ValueError(
                f"Could not fetch exchange rate for {from_curr} to {to_curr}"
            ) from e

    def _extract_close_price(self, df: Any, ticker: str) -> Decimal:
        """Extracts the close price from a yfinance DataFrame, handling MultiIndex.

        Args:
            df (pd.DataFrame): The DataFrame returned by yf.download.
            ticker (str): The ticker symbol to extract the price for.

        Returns:
            Decimal: The close price as a Decimal.

        Raises:
            ValueError: If the close price cannot be extracted.
        """
        close_data = None

        if isinstance(df.columns, pd.MultiIndex):
            if "Close" in df.columns.levels[0] and ticker in df.columns.levels[1]:
                close_data = df["Close"][ticker]
        else:
            if "Close" in df.columns:
                if ticker in df.columns:
                    close_data = df[ticker]
                else:
                    close_data = df["Close"]

        if close_data is None or close_data.empty:
            raise ValueError(f"No close price data found for {ticker}")

        series = close_data.dropna()
        if series.empty:
            raise ValueError(f"No valid close price found for {ticker}")

        try:
            last_value = series.iloc[-1]
            if hasattr(last_value, "item"):
                rate_value = last_value.item()
            elif isinstance(last_value, (int, float)):
                rate_value = last_value
            else:
                rate_value = float(last_value)

            price_decimal = Decimal(str(rate_value))

            return price_decimal

        except (
            ValueError,
            ConversionSyntax,
            AttributeError,
            TypeError,
        ) as e:
            logger.error(
                f"Failed to parse close price for {ticker}: {series.iloc[-1]} "
                f"(type: {type(series.iloc[-1])}) ({e})"
            )
            raise ValueError(f"Could not parse close price for {ticker}") from e
