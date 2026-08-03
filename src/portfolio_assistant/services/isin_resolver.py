"""Yahoo Finance ISIN resolver with round-trip validation.

This module provides a secure ISIN resolver that queries Yahoo Finance API
and validates responses using round-trip ISIN matching.
"""

import logging

from httpx2 import AsyncClient, Response

from portfolio_assistant.services.isin_cache import SQLiteISINCache

logger = logging.getLogger(__name__)


class YahooISINResolver:
    """Yahoo Finance ISIN resolver with SQLite caching.

    Resolves ISINs to ticker symbols using Yahoo Finance search API with
    round-trip validation to ensure accuracy.
    """

    def __init__(self, cache: SQLiteISINCache | None = None):
        """Initialize the ISIN resolver.

        Args:
            cache: Optional SQLiteISINCache instance. If None, creates a new one.
        """
        self.cache = cache or SQLiteISINCache()
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

    async def resolve_isin(self, isin: str) -> str | None:
        """Resolve ISIN to ticker using Yahoo Finance API with round-trip validation.

        Args:
            isin: The ISIN to resolve (e.g., 'US0378331005').

        Returns:
            Optional[str]: The resolved ticker if successful, None if resolution fails.

        Raises:
            Exception: If there's an unexpected error during resolution.
        """
        if not isin or not isin.strip():
            return None

        normalized_isin = isin.strip().upper()

        # Check cache first
        cached_ticker = await self.cache.get_ticker(normalized_isin)
        if cached_ticker:
            logger.debug(f"Cache hit for ISIN {normalized_isin}: {cached_ticker}")
            return cached_ticker

        logger.debug(f"Cache miss for ISIN {normalized_isin}, querying Yahoo Finance")

        try:
            ticker = await self._query_yahoo_api(normalized_isin)
            if ticker:
                # Cache the successful resolution
                await self.cache.set_ticker(normalized_isin, ticker)
                logger.debug(f"Resolved ISIN {normalized_isin} to {ticker} and cached")
                return ticker
            else:
                logger.debug(f"No valid ticker found for ISIN {normalized_isin}")
                return None

        except Exception as e:
            logger.error(f"Error resolving ISIN {normalized_isin}: {str(e)}")
            return None

    async def _query_yahoo_api(self, isin: str) -> str | None:
        """Query Yahoo Finance API and validate response with round-trip matching.

        Args:
            isin: The ISIN to query.

        Returns:
            Optional[str]: The validated ticker if exact ISIN match found,
            None otherwise.
        """
        search_url = (
            f"https://query2.finance.yahoo.com/v1/finance/search?"
            f"q={isin}&quotesCount=5&newsCount=0"
        )

        try:
            async with AsyncClient() as client:
                headers = {"User-Agent": self.user_agent}
                response: Response = await client.get(search_url, headers=headers)

                if response.status_code != 200:
                    logger.warning(f"Yahoo API request failed: {response.status_code}")
                    return None

                data = response.json()

                # Extract quotes from response
                quotes = data.get("quotes", [])
                if not quotes:
                    logger.debug(f"No quotes found for ISIN {isin}")
                    return None

                # Perform round-trip validation: find quote with exact ISIN match
                for quote in quotes:
                    quote_isin = quote.get("isin")
                    if quote_isin and quote_isin.upper() == isin.upper():
                        # Exact ISIN match found - this is a valid resolution
                        ticker = quote.get("symbol")
                        if ticker and isinstance(ticker, str):
                            logger.debug(
                                f"Round-trip validation successful: {isin} -> {ticker}"
                            )
                            return ticker

                logger.debug(f"No exact ISIN match found for {isin} in Yahoo response")
                return None

        except Exception as e:
            logger.error(f"Yahoo API query failed for ISIN {isin}: {str(e)}")
            return None

    async def resolve_isins(self, isins: list[str]) -> dict[str, str | None]:
        """Resolve multiple ISINs efficiently.

        Args:
            isins: List of ISINs to resolve.

        Returns:
            dict[str, Optional[str]]: Mapping of ISIN to resolved ticker (or None).
        """
        results = {}
        for isin in isins:
            results[isin] = await self.resolve_isin(isin)
        return results
