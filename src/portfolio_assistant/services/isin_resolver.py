import logging
import re

import httpx

from portfolio_assistant.services.isin_cache import SQLiteISINCache

logger = logging.getLogger(__name__)


class YahooISINResolver:
    """Resolves ISINs to ticker symbols using Yahoo Finance Search API with caching."""

    YAHOO_FINANCE_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search?q={isin}&quotesCount=1&newsCount=0"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    )

    def __init__(self, isin_cache: SQLiteISINCache | None = None) -> None:
        self.isin_cache = isin_cache or SQLiteISINCache()
        self.http_client = httpx.AsyncClient(headers={"User-Agent": self.USER_AGENT})

    async def resolve(self, isin_or_ticker: str) -> str:
        """Resolves an ISIN or ticker to a standard ticker symbol.

        If the input looks like a ticker (e.g. BAACSG), it's returned as-is.
        If it looks like an ISIN, it's resolved via cache and Yahoo Finance API.

        Args:
            isin_or_ticker (str): The ISIN or ticker to resolve.

        Returns:
            str: The resolved ticker symbol or the original input if resolution fails.
        """
        # If it's already a ticker (not matching ISIN regex), return it
        cleaned_input = isin_or_ticker.strip().upper()
        if not self._is_isin(cleaned_input):
            return cleaned_input

        cleaned_isin = cleaned_input

        # 1. Check local cache first
        cached_ticker = await self.isin_cache.get(cleaned_isin)
        if cached_ticker:
            logger.info(f"ISIN {cleaned_isin} resolved from cache: {cached_ticker}")
            return cached_ticker

        # 2. If not cached, query Yahoo Finance Search API
        try:
            response = await self.http_client.get(
                self.YAHOO_FINANCE_SEARCH_URL.format(isin=cleaned_isin)
            )
            response.raise_for_status()  # Raise an exception for HTTP errors
            data = response.json()

            if data and data["quotes"]:
                ticker = str(data["quotes"][0]["symbol"])
                await self.isin_cache.set(cleaned_isin, ticker)
                logger.info(f"ISIN {cleaned_isin} resolved via Yahoo Finance: {ticker}")
                return ticker
            else:
                logger.warning(
                    f"Yahoo Finance API returned no quotes for ISIN: {cleaned_isin}. "
                    "Returning original ISIN as ticker."
                )
                return cleaned_isin

        except httpx.HTTPStatusError as e:
            logger.warning(
                f"HTTP error resolving ISIN {cleaned_isin} with Yahoo Finance: {e}. "
                "Returning original ISIN as ticker."
            )
        except httpx.RequestError as e:
            logger.warning(
                f"Network error resolving ISIN {cleaned_isin} with Yahoo Finance: {e}. "
                "Returning original ISIN as ticker."
            )
        except Exception as e:
            logger.warning(
                f"Unexpected error resolving ISIN {cleaned_isin} "
                f"with Yahoo Finance: {e}. "
                "Returning original ISIN as ticker."
            )

        # 3. Fail-safe Fallback
        return cleaned_isin

    def _is_isin(self, value: str) -> bool:
        """Checks if the value matches the ISIN format."""
        return bool(re.fullmatch(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$", value))

    def _clean_and_validate_isin(self, isin: str) -> str:
        """Cleans and validates the ISIN.

        Args:
            isin (str): The raw ISIN string.

        Returns:
            str: The cleaned and validated ISIN.

        Raises:
            ValueError: If the ISIN is invalid.
        """
        cleaned_isin = isin.strip().upper()
        if not self._is_isin(cleaned_isin):
            raise ValueError(f"Invalid ISIN format: {isin}")
        return cleaned_isin
