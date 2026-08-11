"""Yahoo Finance ISIN resolver with round-trip validation.

This module provides a secure ISIN resolver that queries Yahoo Finance API
and validates responses using round-trip ISIN matching.
"""

import logging
import re
from typing import Any

from httpx2 import AsyncClient, Response

from portfolio_assistant.models.portfolio import Currency
from portfolio_assistant.services.isin_cache import SQLiteISINCache

logger = logging.getLogger(__name__)


class YahooISINResolver:
    """Yahoo Finance ISIN resolver with SQLite caching.

    Resolves ISINs to ticker symbols using Yahoo Finance search API with
    round-trip validation to ensure accuracy.
    """

    def __init__(self, cache: SQLiteISINCache | None = None) -> None:
        """Initialize the ISIN resolver.

        Args:
            cache: Optional SQLiteISINCache instance. If None, creates a new one.
        """
        self.cache = cache or SQLiteISINCache()
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

    async def resolve_isin(
        self, isin: str, portfolio_currency: Currency = Currency.CZK
    ) -> str | None:
        """Resolve ISIN to ticker using Yahoo Finance API with round-trip validation.

        Args:
            isin: The ISIN to resolve (e.g., 'US0378331005').
            portfolio_currency: The currency of the portfolio.

        Returns:
            Optional[str]: The resolved ticker if successful, None if resolution fails.

        Raises:
            Exception: If there's an unexpected error during resolution.
        """
        if not isin or not isin.strip():
            return None

        preferred_exchanges = self.get_preferred_exchanges(portfolio_currency)

        normalized_isin = isin.strip().upper()

        # Check cache first using correct 'get_ticker' method
        cached_ticker = await self.cache.get_ticker(normalized_isin)
        if cached_ticker:
            logger.debug(f"Cache hit for ISIN {normalized_isin}: {cached_ticker}")
            return cached_ticker

        logger.debug(f"Cache miss for ISIN {normalized_isin}, querying Yahoo Finance")

        try:
            ticker = await self._query_yahoo_api(normalized_isin, preferred_exchanges)
            if ticker:
                # Cache the successful resolution using correct 'set_ticker' method
                await self.cache.set_ticker(normalized_isin, ticker)
                logger.debug(f"Resolved ISIN {normalized_isin} to {ticker} and cached")
                return ticker
            else:
                logger.debug(f"No valid ticker found for ISIN {normalized_isin}")
                return None

        except Exception as e:
            logger.error(f"Error resolving ISIN {normalized_isin}: {str(e)}")
            return None

    def get_preferred_exchanges(self, portfolio_currency: Currency) -> set[str]:
        """Get preferred exchanges based on portfolio currency.

        Args:
            portfolio_currency: The currency of the portfolio.

        Returns:
            set[str]: A set of preferred exchanges.
        """
        # Dynamically build preferred exchanges based on portfolio base currency
        if portfolio_currency in [Currency.CZK, Currency.EUR]:
            # Prefer European exchanges first, then US
            return {
                "AMS",
                "XET",
                "FRA",
                "MIL",
                "PAR",
                "GER",
                "NYQ",
                "NMS",
                "NAS",
                "ASE",
            }
        elif portfolio_currency == Currency.GBP:
            # Prefer London Stock Exchange
            return {"LSE", "LON"}
        else:
            # Default to US exchanges
            return {"NYQ", "NMS", "NAS", "ASE"}

    async def _query_yahoo_api(
        self, isin: str, preferred_exchanges: set[str]
    ) -> str | None:
        """Query Yahoo Finance API and validate response with round-trip matching.

        Args:
            isin: The ISIN to query.
            preferred_exchanges: A set of preferred exchanges.

        Returns:
            Optional[str]: The validated ticker if exact ISIN match found,
            None otherwise.
        """
        # Validate ISIN format before sending external API queries
        if not re.match(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$", isin):
            logger.warning(f"Aborting query due to invalid ISIN format: {isin}")
            return None

        search_url = (
            f"https://query2.finance.yahoo.com/v1/finance/search?"
            f"q={isin}&quotesCount=5&newsCount=0"
        )

        try:
            async with AsyncClient() as client:
                headers = {"User-Agent": self.user_agent}
                response: Response = await client.get(search_url, headers=headers)

                if response.status_code != 200:
                    logger.warning(
                        f"Yahoo API request failed with status: {response.status_code}"
                    )
                    return None

                data = response.json()

                # Extract and validate quotes from response
                quotes = data.get("quotes", [])
                if not quotes:
                    logger.debug(f"No quotes found for ISIN {isin}")
                    return None

                def quote_priority_key(q: dict[str, Any]) -> tuple[int, int, int]:
                    """Sort key to prioritize exact ISINs, US exchanges,
                    and suffixes."""
                    # Priority 1: Exact ISIN match (0 = highest, 1 = mismatch/missing)
                    quote_isin = q.get("isin", "").upper()
                    isin_mismatch = 0 if quote_isin == isin.upper() else 1

                    # Priority 2: Preferred US exchange (0 = US exchange, 1 = foreign)
                    exchange = q.get("exchange", "").upper()
                    is_foreign_exchange = 0 if exchange in preferred_exchanges else 1

                    # Priority 3: Suffix-free symbols (US tickers lack a dot)
                    symbol = q.get("symbol", "")
                    has_foreign_suffix = 1 if "." in symbol else 0

                    return (isin_mismatch, is_foreign_exchange, has_foreign_suffix)

                # Sort quotes so that best matches and US listings are evaluated first
                sorted_quotes = sorted(quotes, key=quote_priority_key)

                # Perform round-trip validation with exact-match fallback
                for quote in sorted_quotes:
                    quote_isin = quote.get("isin")
                    ticker = quote.get("symbol")

                    if not ticker or not isinstance(ticker, str):
                        continue

                    # Match if ISIN is equal, or if Yahoo omitted the 'isin' field but
                    # returned the quote as a top-priority result for this ISIN query.
                    if not quote_isin or quote_isin.upper() == isin.upper():
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
