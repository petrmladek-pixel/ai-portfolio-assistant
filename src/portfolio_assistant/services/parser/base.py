"""Abstract base parser for portfolio files.

This module defines the base interface for all broker-specific portfolio parsers,
providing both synchronous and asynchronous parsing capabilities, along with common
helper methods for parsing and cleaning financial data.
"""

import asyncio
import csv
from abc import ABC, abstractmethod
from decimal import Decimal
from io import StringIO

from portfolio_assistant.models.portfolio import ImportedPortfolio
from portfolio_assistant.services.isin_resolver import YahooISINResolver


class BasePortfolioParser(ABC):
    """Abstract base class for all portfolio parsers.

    Defines the contract for parsing portfolio files from different brokers
    into a standardized ImportedPortfolio model, along with common helper methods.
    """

    def __init__(self, isin_resolver: YahooISINResolver | None = None) -> None:
        """Initialize the base parser with an optional ISIN resolver.

        Args:
            isin_resolver: Optional YahooISINResolver instance.
        """
        self.isin_resolver = isin_resolver or YahooISINResolver()

    @property
    @abstractmethod
    def broker_name(self) -> str:
        """Return the name of the broker this parser handles.

        Returns:
            str: The name of the broker (e.g., 'DEGIRO', 'Fio e-Broker').
        """

    @abstractmethod
    def parse_sync(self, file_content: bytes) -> ImportedPortfolio:
        """Synchronously parse the content of a portfolio file.

        Args:
            file_content (bytes): The raw binary content of the portfolio file.

        Returns:
            ImportedPortfolio: The parsed and validated portfolio data.
        """

    async def parse_async(self, file_content: bytes) -> ImportedPortfolio:
        """Asynchronously parse the content of a portfolio file.

        Args:
            file_content (bytes): The raw binary content of the portfolio file.

        Returns:
            ImportedPortfolio: The parsed and validated portfolio data.
        """
        return await asyncio.to_thread(self.parse_sync, file_content)

    def safe_decode(
        self, file_content: bytes, fallback_encoding: str = "windows-1250"
    ) -> str:
        """Safely decode bytes to string with UTF-8 and fallback encoding.

        Args:
            file_content: The raw binary content to decode.
            fallback_encoding: The encoding to use if UTF-8 fails.

        Returns:
            str: The decoded string content.
        """
        try:
            return file_content.decode("utf-8-sig")
        except UnicodeDecodeError:
            return file_content.decode(fallback_encoding)

    def clean_decimal(self, value: str) -> Decimal:
        """Clean and convert numeric strings to Decimal, handling various formats.

        Handles:
        - Spaces and non-breaking spaces
        - Czech decimal formatting (comma as decimal separator)
        - Thousands separators
        - Empty strings and None values

        Args:
            value: The string value to convert to Decimal.

        Returns:
            Decimal: The cleaned and converted decimal value.
        """
        if not value or not value.strip():
            return Decimal("0.00")

        # Remove spaces, non-breaking spaces, and thousands separators
        cleaned = value.replace(" ", "").replace("\xa0", "").replace(",", ".").strip()

        # Handle cases where multiple dots might exist from thousands separators
        if cleaned.count(".") > 1:
            parts = cleaned.split(".")
            cleaned = "".join(parts[:-1]) + "." + parts[-1]

        try:
            return Decimal(cleaned)
        except Exception:
            return Decimal("0.00")

    def _prepare_csv_reader(
        self,
        file_content: bytes,
        delimiter: str | None = None,
        fallback_encoding: str = "windows-1250",
    ) -> tuple[csv.DictReader[str], list[str]]:
        """Decodes CSV content and returns a safe DictReader with trimmed headers.

        Args:
            file_content: The raw binary content.
            delimiter: Optional explicit delimiter to use.
            fallback_encoding: Encoding fallback if UTF-8 fails.

        Returns:
            tuple: A DictReader and a list of trimmed headers.
        """
        decoded_content = self.safe_decode(
            file_content, fallback_encoding=fallback_encoding
        )
        lines = decoded_content.strip().splitlines()
        if not lines:
            raise ValueError("Empty file content provided.")

        # Heuristic delimiter detection if not explicitly specified
        if delimiter is None:
            delimiter = ";" if ";" in lines[0] else ","

        csv_file = StringIO(decoded_content)
        reader = csv.DictReader(csv_file, delimiter=delimiter)

        headers = [h.strip() for h in (reader.fieldnames or [])]
        return reader, headers
