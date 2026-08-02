import asyncio
import csv
import re
from datetime import datetime
from decimal import Decimal
from io import StringIO

from portfolio_assistant.models.portfolio import (
    Currency,
    ImportedPortfolio,
    StockPosition,
)
from portfolio_assistant.services.isin_resolver import YahooISINResolver
from portfolio_assistant.services.parser.base import BasePortfolioParser


class DegiroPortfolioParser(BasePortfolioParser):
    def __init__(self, isin_resolver: YahooISINResolver | None = None) -> None:
        self.isin_resolver = isin_resolver or YahooISINResolver()

    @property
    def broker_name(self) -> str:
        return "DEGIRO"

    def parse_sync(self, file_content: bytes) -> ImportedPortfolio:
        return asyncio.run(self.parse_async_internal(file_content))

    async def parse_async_internal(self, file_content: bytes) -> ImportedPortfolio:
        # Decode with UTF-8, handling BOM
        decoded_content = file_content.decode("utf-8-sig")
        lines = decoded_content.strip().splitlines()

        if not lines:
            raise ValueError("Empty file content provided.")

        # Detect delimiter by checking the first line for semicolons
        delimiter = ";" if ";" in lines[0] else ","

        # Prepare CSV reader
        csv_file = StringIO(decoded_content)
        reader = csv.reader(csv_file, delimiter=delimiter)

        headers = [header.strip() for header in next(reader)]

        # Map localized headers to internal keys
        header_map = self._map_headers(headers)
        if not all(
            key in header_map
            for key in ["product_name", "symbol_isin", "quantity", "average_price"]
        ):
            raise ValueError(
                "Missing essential columns in the CSV file. Required: Product Name, "
                "Symbol/ISIN, Quantity, Average Price"
            )

        positions: list[StockPosition] = []
        for row in reader:
            if not row or all(not cell.strip() for cell in row):
                continue  # Skip empty rows

            row_data = dict(zip(headers, row, strict=False))

            # Filter out cash balances (support both English and Czech)
            product_name = row_data.get(header_map["product_name"], "").strip()
            product_name_lower = product_name.lower()
            if "cash" in product_name_lower or "hotovost" in product_name_lower:
                continue

            try:
                quantity = self._clean_decimal(
                    row_data.get(header_map["quantity"], "0")
                )
                average_price = self._clean_decimal(
                    row_data.get(header_map["average_price"], "0")
                )
            except Exception as e:
                print(f"Skipping row due to numeric parsing error: {row}. Error: {e}")
                continue  # Skip if quantity or price are not valid numbers

            # Only include positions with positive quantity and average price
            if quantity <= 0 or average_price <= 0:
                continue

            symbol_isin = row_data.get(header_map["symbol_isin"], "").strip()
            ticker = await self._resolve_ticker(symbol_isin)

            # Determine currency
            currency = self._determine_currency(row_data, header_map)

            positions.append(
                StockPosition(
                    ticker=ticker,
                    name=product_name,
                    quantity=quantity,
                    average_price=average_price,
                    currency=currency,
                )
            )

        # Create an ImportedPortfolio instance
        imported_portfolio = ImportedPortfolio(
            broker_name=self.broker_name,
            imported_at=datetime.now(),
            positions=positions,
        )

        return imported_portfolio

    def _map_headers(self, headers: list[str]) -> dict[str, str]:
        """Maps localized headers to internal standard keys."""
        header_map = {}
        for header in headers:
            normalized_header = header.strip().lower()
            if normalized_header in ["produkt", "product", "asset"]:
                header_map["product_name"] = header
            elif normalized_header in ["symbol/isin", "symbool/isin", "symbol", "isin"]:
                header_map["symbol_isin"] = header
            elif normalized_header in ["množství", "aantal", "quantity", "pozice"]:
                header_map["quantity"] = header
            elif normalized_header in [
                "bpe",
                "bep",
                "break-even price",
                "průměrná cena",
                "průměrný kurz",
                "average price",
                "uzavírací",
                "closing price",
            ]:
                header_map["average_price"] = header
            elif normalized_header in ["měna", "valuta", "currency, hodnota"]:
                header_map["currency"] = header
        return header_map

    def _clean_decimal(self, value: str) -> Decimal:
        """Cleans numeric strings and converts them to Decimal."""
        cleaned_value = value.replace(",", ".")
        return Decimal(cleaned_value)

    async def _resolve_ticker(self, symbol_isin: str) -> str:
        """Resolves ticker from Symbol/ISIN using the YahooISINResolver or extracting
        from string.
        """
        if not symbol_isin:
            return "N/A"

        # ISIN pattern: 2 letters, 10 alphanumeric chars (e.g., US0378331005)
        if re.fullmatch(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$", symbol_isin, re.IGNORECASE):
            try:
                return await self.isin_resolver.resolve(symbol_isin)
            except ValueError:  # Invalid ISIN format caught by resolver
                return symbol_isin.upper()

        # Try to extract ticker from combined symbol/ISIN (e.g., "AAPL - US0378331005")
        match = re.match(
            r"^([A-Z0-9.-]+)\s*[-–—]?\s*[A-Z]{2}[A-Z0-9]{9}[0-9]$",
            symbol_isin,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).strip().upper()  # Return the ticker part

        # Fallback to using the symbol_isin itself if it looks like a ticker
        if re.fullmatch(r"^[A-Z0-9.-]{1,10}$", symbol_isin, re.IGNORECASE):
            return symbol_isin.upper()

        return symbol_isin.upper()  # Default fallback

    def _determine_currency(
        self,
        row_data: dict[str, str],
        header_map: dict[str, str],
    ) -> Currency:
        """Determines the currency from the row data or defaults to EUR."""
        if "currency" in header_map and header_map["currency"] in row_data:
            currency_str = row_data[header_map["currency"]].strip().upper()
            try:
                return Currency(currency_str)
            except ValueError:
                pass  # Fall through to other methods if direct conversion fails

        # Attempt to parse currency from average price string if a symbol is present
        if "average_price" in header_map and header_map["average_price"] in row_data:
            price_str = row_data[header_map["average_price"]].strip()
            if "€" in price_str or "EUR" in price_str.upper():
                return Currency.EUR
            elif "$" in price_str or "USD" in price_str.upper():
                return Currency.USD
            elif "Kč" in price_str or "CZK" in price_str.upper():
                return Currency.CZK

        # Check all other columns for currency symbols (for CSV formats like DEGIRO CZ)
        for header, value in row_data.items():
            if not value or not header:
                continue

            value_upper = value.strip().upper()
            if "EUR" in value_upper or "€" in value:
                return Currency.EUR
            elif "USD" in value_upper or "$" in value:
                return Currency.USD
            elif "CZK" in value_upper or "Kč" in value_upper:
                return Currency.CZK

        # Default to EUR if no currency column or symbol found
        return Currency.EUR
