"""Fio e-Broker CSV parser.

This module provides a parser for Fio e-Broker CSV exports with support for
CP1250/UTF-8 encodings, semicolon delimiters, and Czech decimal formatting.
"""

import csv
import io
from collections.abc import Iterator
from decimal import Decimal

from portfolio_assistant.core.utils import get_now_utc
from portfolio_assistant.models.portfolio import (
    Currency,
    ImportedPortfolio,
    StockPosition,
)
from portfolio_assistant.services.isin_resolver import YahooISINResolver
from portfolio_assistant.services.parser.base import BasePortfolioParser


class FioBrokerPortfolioParser(BasePortfolioParser):
    """Parser for Fio e-Broker CSV exports."""

    # Local mappings to resolve Fio's Czech symbols instantly without API queries
    FIO_LOCAL_MAPPINGS = {
        "BAACSG": "CSG.PR",  # Colt CZ Group
        "BAACEZ": "CEZ.PR",  # CEZ
        "BAAKOMB": "KOMB.PR",  # Komercni banka
        "BAAGECBA": "MONET.PR",  # Moneta Money Bank
        "BAAMONET": "MONET.PR",  # Moneta Money Bank
        "BAAERST": "ERSTE.PR",  # Erste Group Bank
        "BAAVIG": "VIG.PR",  # Vienna Insurance Group
        "BAAPEN": "PEN.PR",  # Photon Energy
        "BAATABAC": "TABAK.PR",  # Philip Morris CR
        "BAAPILUL": "PILULKA.PR",  # Pilulka Lekarny
        "BAAKOFOL": "KOFOL.PR",  # Kofola CS
    }

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
            elif norm in ["symbol", "značka", "ticker", "značka;"]:
                header_map["symbol"] = header
            elif norm in ["množství", "quantity", "počet", "kusy"]:
                header_map["quantity"] = header
            elif norm in ["cena", "price", "kurz", "průměrná cena"]:
                header_map["price"] = header
            elif norm in ["měna", "currency", "valuta"]:
                header_map["currency"] = header
            elif norm in ["nákup", "nákupní hodnota", "nakup"]:
                header_map["total_purchase"] = header
        return header_map

    def _prepare_and_validate(
        self, file_content: bytes
    ) -> tuple[csv.DictReader[str], dict[str, str]]:
        """Prepares reader and validates that minimum headers exist.

        Raises:
            ValueError: If essential columns are missing.
        """
        # Try standard prepared reader first (auto-decoding)
        reader, headers = self._prepare_csv_reader(file_content, delimiter=";")
        header_map = self._map_headers(headers)

        # Validate we have Symbol or ISIN, Quantity, and either direct Price or Purchase
        has_id = "symbol" in header_map or "isin" in header_map
        has_price = "price" in header_map or "total_purchase" in header_map
        has_qty = "quantity" in header_map

        # If mapping failed, try forced CP1250 decoding (common for Fio exports)
        if not (has_id and has_price and has_qty):
            try:
                decoded = file_content.decode("cp1250")
                # Simple logic to find the header row if it's a
                # "Portfolio - Vyvoj" format
                lines = decoded.splitlines()
                header_line_idx = 0
                for i, line in enumerate(lines):
                    if "Symbol;" in line or "Značka;" in line or "ISIN;" in line:
                        header_line_idx = i
                        break

                actual_content = "\n".join(lines[header_line_idx:])
                csv_file = io.StringIO(actual_content)
                reader = csv.DictReader(csv_file, delimiter=";")
                headers = [h.strip() for h in (reader.fieldnames or [])]
                header_map = self._map_headers(headers)
            except Exception:
                pass

        # Final validation
        has_id = "symbol" in header_map or "isin" in header_map
        has_price = "price" in header_map or "total_purchase" in header_map
        has_qty = "quantity" in header_map

        if not (has_id and has_price and has_qty):
            raise ValueError(
                "Missing essential columns in the Fio e-Broker CSV file. "
                "Required: Symbol/ISIN, Quantity, and Price/Purchase Value"
            )

        return reader, header_map

    def _clean_rows_generator(
        self, reader: csv.DictReader[str], header_map: dict[str, str]
    ) -> Iterator[tuple[str, str, Decimal, Decimal, Currency]]:
        """Common generator that decodes, filters, and sanitizes each Fio CSV row."""
        for row in reader:
            if not row or all(not cell.strip() for cell in row.values()):
                continue

            symbol = row.get(header_map.get("symbol", ""), "").strip()
            # Skip common currency rows (like 'CZK' cash/liquidity position row)
            if symbol.upper() == "CZK":
                continue

            isin = row.get(header_map.get("isin", ""), "").strip()
            quantity_str = row.get(header_map.get("quantity", ""), "0")

            if not symbol and not isin:
                continue

            try:
                quantity = self.clean_decimal(quantity_str)
                if quantity <= 0:
                    continue

                # Determine average price (either from Price or Total Purchase Value)
                if "price" in header_map:
                    price_str = row.get(header_map["price"], "0")
                    average_price = self.clean_decimal(price_str)
                elif "total_purchase" in header_map:
                    total_purchase_str = row.get(header_map["total_purchase"], "0")
                    total_purchase = self.clean_decimal(total_purchase_str)
                    average_price = total_purchase / quantity
                else:
                    continue
            except Exception:
                print("Skipping row due to numeric parsing error")
                continue

            if average_price <= 0:
                continue

            # Determine currency (Fio usually defaults to CZK)
            currency = Currency.CZK
            if "currency" in header_map:
                currency_str = row.get(header_map["currency"], "CZK").strip().upper()
                if currency_str in Currency.__members__:
                    currency = Currency[currency_str]

            yield isin, symbol, quantity, average_price, currency

    async def parse(self, file_content: bytes) -> ImportedPortfolio:
        reader, header_map = self._prepare_and_validate(file_content)
        positions: list[StockPosition] = []

        for isin, symbol, qty, price, currency in self._clean_rows_generator(
            reader, header_map
        ):
            if symbol:
                symbol_upper = symbol.upper()
                if symbol_upper in self.FIO_LOCAL_MAPPINGS:
                    ticker = self.FIO_LOCAL_MAPPINGS[symbol_upper]
                else:
                    ticker = symbol_upper
                name = symbol
            elif isin:
                resolved_ticker = await self.isin_resolver.resolve_isin(isin)
                if resolved_ticker:
                    ticker = resolved_ticker
                    name = f"Asset {isin}"
                else:
                    # First-class Unknown handling (Zewei's advice)
                    ticker = "UNKNOWN"
                    name = f"Unknown Asset (ISIN: {isin})"
                    qty = Decimal("0.00")
                    price = Decimal("0.00")
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
            imported_at=get_now_utc(),
            positions=positions,
        )
