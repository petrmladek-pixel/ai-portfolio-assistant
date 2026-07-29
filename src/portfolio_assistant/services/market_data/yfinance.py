"""Yahoo Finance market data service implementation.

This module provides a concrete implementation of the BaseMarketDataService
using the yfinance library to fetch current prices and exchange rates.
"""

import asyncio
import logging
from decimal import ConversionSyntax, Decimal

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

        # Normalize single-ticker vs multi-ticker download results
        if isinstance(df.columns, pd.MultiIndex):
            # Multi-ticker downloads return columns with a MultiIndex:
            # e.g., ('Close', 'AAPL')
            if "Close" in df.columns.levels[0]:
                close_df = df["Close"]
                for ticker in tickers_upper:
                    if ticker in close_df.columns:
                        series = close_df[ticker].dropna()
                        if not series.empty:
                            prices[ticker] = Decimal(str(series.iloc[-1]))
        else:
            # Single ticker download returns columns like:
            # ['Open', 'High', 'Low', 'Close', ...]
            if "Close" in df.columns:
                series = df["Close"].dropna()
                if not series.empty and len(tickers_upper) == 1:
                    prices[tickers_upper[0]] = Decimal(str(series.iloc[-1]))

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

        if (
            df is not None
            and isinstance(df, pd.DataFrame)
            and not df.empty
            and "Close" in df.columns
        ):
            series = df["Close"].dropna()
            if not series.empty:
                try:
                    # Get the last value from the series, ensuring it's a scalar
                    last_value = series.iloc[-1]

                    # Handle different types that yfinance might return
                    if hasattr(last_value, "item"):  # pandas Series
                        rate_value = last_value.item()
                    elif isinstance(last_value, (int, float)):
                        rate_value = last_value
                    else:
                        # Try to extract scalar value from various pandas types
                        rate_value = float(last_value)

                    return Decimal(str(rate_value))
                except (ValueError, ConversionSyntax, AttributeError, TypeError) as e:
                    logger.error(
                        f"Failed to parse exchange rate {from_curr}->{to_curr}: "
                        f"{series.iloc[-1]} (type: {type(series.iloc[-1])}) ({e})"
                    )
                    raise ValueError(
                        f"Could not parse exchange rate for {from_curr} to {to_curr}"
                    ) from e

        raise ValueError(f"Could not fetch exchange rate for {from_curr} to {to_curr}")
