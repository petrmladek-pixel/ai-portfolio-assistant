"""Abstract base parser for portfolio files.

This module defines the base interface for all broker-specific portfolio parsers,
providing both synchronous and asynchronous parsing capabilities, along with common
helper methods for parsing and cleaning financial data.
"""

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
    async def parse(self, file_content: bytes) -> ImportedPortfolio:
        """Asynchronously parse the content of a portfolio file.

        Args:
            file_content (bytes): The raw binary content of the portfolio file.

        Returns:
            ImportedPortfolio: The parsed and validated portfolio data.
        """

    def safe_decode(self, file_content: bytes) -> str:
        """Safely decode bytes to string, automatically detecting the encoding.

        Uses the 'charset-normalizer' library (already installed in the project
        as a dependency of httpx2) to detect the best encoding match, with a
        robust manual fallback chain (utf-8-sig -> windows-1250 -> latin1)
        if detection fails.

        Args:
            file_content: The raw binary content to decode.

        Returns:
            str: The decoded string content.
        """
        import charset_normalizer

        # 1. Attempt automatic encoding detection
        try:
            match = charset_normalizer.from_bytes(file_content).best()
            if match is not None:
                # charset-normalizer automatically handles BOM markers
                return str(match)
        except Exception:
            # Fall back to manual chain on unexpected detection error
            pass

        # 2. Strict manual fallback chain
        try:
            return file_content.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                return file_content.decode("windows-1250")
            except UnicodeDecodeError:
                # Last resort: latin1 never fails but might produce junk
                return file_content.decode("latin1")

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

        Raises:
            decimal.InvalidOperation: If the value cannot be parsed as a Decimal.
        """
        if not value or not value.strip():
            return Decimal("0.00")

        # Remove spaces, non-breaking spaces, and thousands separators
        cleaned = value.replace(" ", "").replace("\xa0", "").replace(",", ".").strip()

        # Handle cases where multiple dots might exist from thousands separators
        if cleaned.count(".") > 1:
            parts = cleaned.split(".")
            cleaned = "".join(parts[:-1]) + "." + parts[-1]

        return Decimal(cleaned)

    def _prepare_csv_reader(
        self,
        file_content: bytes,
        delimiter: str | None = None,
    ) -> tuple[csv.DictReader[str], list[str]]:
        """Decodes CSV content and returns a safe DictReader with trimmed headers.

        Args:
            file_content: The raw binary content.
            delimiter: Optional explicit delimiter to use.

        Returns:
            tuple: A DictReader and a list of trimmed headers.
        """
        decoded_content = self.safe_decode(file_content)
        lines = decoded_content.strip().splitlines()
        if not lines:
            raise ValueError("Empty file content provided.")

        # If this is a Fio e-Broker file starting with metadata lines, skip them
        # to reach the header row.
        # Check if "Portfolio - Vývoj" or similar starts the file.
        actual_content = decoded_content
        for idx, line in enumerate(lines):
            line_lower = line.lower()
            if (
                "symbol;" in line_lower
                or "isin;" in line_lower
                or "značka;" in line_lower
                or "značka" in line_lower
            ):
                actual_content = "\n".join(lines[idx:])
                break

        lines = actual_content.strip().splitlines()
        if not lines:
            raise ValueError("Empty file content provided after skipping metadata.")

        # Heuristic delimiter detection if not explicitly specified
        if delimiter is None:
            delimiter = ";" if ";" in lines[0] else ","

        csv_file = StringIO(actual_content)
        reader = csv.DictReader(csv_file, delimiter=delimiter)

        headers = [h.strip() for h in (reader.fieldnames or [])]
        return reader, headers
