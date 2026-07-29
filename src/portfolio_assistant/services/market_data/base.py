"""Abstract base class for market data services.

This module defines the interface for fetching current market prices
and currency exchange rates from various financial data providers.
"""

from abc import ABC, abstractmethod
from decimal import Decimal


class BaseMarketDataService(ABC):
    """Abstract base class for market data services."""

    @abstractmethod
    async def get_current_prices(self, tickers: list[str]) -> dict[str, Decimal]:
        """Fetch current market prices for a list of tickers asynchronously.

        Args:
            tickers (list[str]): A list of ticker symbols.

        Returns:
            dict[str, Decimal]: A dictionary mapping each ticker (uppercase)
                to its current price as a Decimal.
        """

    @abstractmethod
    async def get_exchange_rate(self, from_currency: str, to_currency: str) -> Decimal:
        """Fetch currency exchange rate between two currencies asynchronously.

        Args:
            from_currency (str): The currency to convert from (e.g., USD).
            to_currency (str): The currency to convert to (e.g., CZK).

        Returns:
            Decimal: The exchange rate as a Decimal.
        """
