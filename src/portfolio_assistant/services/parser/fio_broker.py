"""Fio e-Broker CSV parser.

This module provides a parser for Fio e-Broker CSV exports with support for
CP1250/UTF-8 encodings, semicolon delimiters, and Czech decimal formatting.
"""

import csv
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal

from portfolio_assistant.models.portfolio import (
    Currency,
    ImportedPortfolio,
    StockPosition,
)
from portfolio_assistant.services.isin_resolver import YahooISINResolver
from portfolio_assistant.services.parser.base import BasePortfolioParser


class FioBrokerPortfolioParser(BasePortfolioParser):
    """Parser for Fio e-Broker CSV exports."""

    def __init__(self, isin_resolver: YahooISINResolver | None = None) -> None:
        """Initialize the Fio e-Broker parser with optional ISIN resolver.

        Args:
            isin_resolver: Optional YahooISINResolver instance.
        """
        super().__init__(isin_resolver)

    @property
    def broker_name(self) -> str:
        return "Fio e-Broker"

    def _map_headers(self, headers: list[str]) -> dict[str, str]:
        """Maps Fio e-Broker headers to internal standard keys."""
        header_map = {}
        for header in headers:
            norm = header.strip().lower()
            if norm in ["isin", "isin kód"]:
                header_map["isin"] = header
            elif norm in ["symbol", "značka", "ticker"]:
                header_map["symbol"] = header
            elif norm in ["množství", "quantity", "počet"]:
                header_map["quantity"] = header
            elif norm in ["cena", "price", "kurz", "průměrná cena"]:
                header_map["price"] = header
            elif norm in ["měna", "currency", "valuta"]:
                header_map["currency"] = header
        return header_map

    def _clean_rows_generator(
        self, reader: csv.DictReader[str], header_map: dict[str, str]
    ) -> Iterator[tuple[str, str, Decimal, Decimal, Currency]]:
        """Common generator that decodes, filters, and sanitizes each Fio CSV row."""
        for row in reader:
            if not row or all(not cell.strip() for cell in row.values()):
                continue

            isin = row.get(header_map["isin"], "").strip()
            symbol = row.get(header_map["symbol"], "").strip()
            quantity_str = row.get(header_map["quantity"], "0")
            price_str = row.get(header_map["price"], "0")
            currency_str = row.get(header_map["currency"], "CZK").strip()

            try:
                quantity = self.clean_decimal(quantity_str)
                average_price = self.clean_decimal(price_str)
            except Exception:
                print("Skipping row due to numeric parsing error")
                continue

            if quantity <= 0 or average_price <= 0:
                continue

            # Determine currency
            try:
                currency = Currency(currency_str.upper())
            except ValueError:
                currency = Currency.CZK

            yield isin, symbol, quantity, average_price, currency

    def parse_sync(self, file_content: bytes) -> ImportedPortfolio:
        reader, headers = self._prepare_csv_reader(
            file_content, delimiter=";", fallback_encoding="cp1250"
        )
        header_map = self._map_headers(headers)

        required_keys = ["isin", "symbol", "quantity", "price", "currency"]
        if not all(k in header_map for k in required_keys):
            raise ValueError(
                "Missing essential columns in the Fio e-Broker CSV file. "
                "Required: ISIN, Symbol, Quantity, Price, Currency"
            )

        positions: list[StockPosition] = []
        for isin, symbol, qty, price, currency in self._clean_rows_generator(
            reader, header_map
        ):
            # Prefer symbol if available, fall back to raw ISIN
            if symbol:
                ticker = symbol.upper()
                name = symbol
            elif isin:
                ticker = isin.upper()
                name = f"Asset {isin}"
            else:
                continue

            positions.append(
                StockPosition(
                    ticker=ticker,
                    name=name,
                    quantity=qty,
                    average_price=price,
                    currency=currency,
                )
            )

        return ImportedPortfolio(
            broker_name=self.broker_name,
            imported_at=datetime.now(),
            positions=positions,
        )

    async def parse_async(self, file_content: bytes) -> ImportedPortfolio:
        reader, headers = self._prepare_csv_reader(
            file_content, delimiter=";", fallback_encoding="cp1250"
        )
        header_map = self._map_headers(headers)

        required_keys = ["isin", "symbol", "quantity", "price", "currency"]
        if not all(k in header_map for k in required_keys):
            raise ValueError(
                "Missing essential columns in the Fio e-Broker CSV file. "
                "Required: ISIN, Symbol, Quantity, Price, Currency"
            )

        positions: list[StockPosition] = []
        for isin, symbol, qty, price, currency in self._clean_rows_generator(
            reader, header_map
        ):
            if symbol:
                ticker = symbol.upper()
                name = symbol
            elif isin:
                # Use YahooISINResolver for exact match round-trip validation
                resolved_ticker = await self.isin_resolver.resolve_isin(isin)
                if resolved_ticker:
                    ticker = resolved_ticker
                    name = f"Asset {isin}"
                else:
                    # First-class Unknown handling (Zewei's advice)
                    # Skip positions with unresolved ISINs to avoid validation errors
                    continue
            else:
                continue

            positions.append(
                StockPosition(
                    ticker=ticker,
                    name=name,
                    quantity=qty,
                    average_price=price,
                    currency=currency,
                )
            )

        return ImportedPortfolio(
            broker_name=self.broker_name,
            imported_at=datetime.now(),
            positions=positions,
        )
