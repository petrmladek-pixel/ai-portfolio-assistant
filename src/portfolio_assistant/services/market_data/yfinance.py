"""Yahoo Finance market data service implementation.

This module provides a concrete implementation of the BaseMarketDataService
using the yfinance library to fetch current prices and exchange rates.
"""

import asyncio
import logging
from decimal import ConversionSyntax, Decimal
from typing import Any

import pandas as pd
import yfinance as yf

from portfolio_assistant.services.market_data.base import BaseMarketDataService

logger = logging.getLogger(__name__)


class YFinanceMarketDataService(BaseMarketDataService):
    """Market data service using Yahoo Finance."""

    async def get_current_prices(self, tickers: list[str]) -> dict[str, Decimal]:
        """Fetch current market prices for a list of tickers asynchronously.

        Args:
            tickers (list[str]): A list of ticker symbols.

        Returns:
            dict[str, Decimal]: A dictionary mapping each ticker (uppercase)
                to its current price as a Decimal.
        """
        if not tickers:
            return {}

        tickers_upper = [t.upper() for t in tickers]

        # yf.download performs synchronous network I/O; wrap in asyncio.to_thread
        df = await asyncio.to_thread(
            yf.download,
            tickers_upper,
            period="1d",
            progress=False,
        )

        prices: dict[str, Decimal] = {}
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return prices

        for ticker in tickers_upper:
            try:
                price = self._extract_close_price(df, ticker)
                prices[ticker] = price
            except ValueError:
                logger.warning(f"Could not fetch price for ticker: {ticker}")
                continue

        # Check for missing tickers
        missing = set(tickers_upper) - set(prices.keys())
        if missing:
            msg = f"Could not fetch prices for tickers: {', '.join(sorted(missing))}"
            logger.warning(msg)
            raise ValueError(msg)

        return prices

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
            return Decimal(str(rate_value))
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
