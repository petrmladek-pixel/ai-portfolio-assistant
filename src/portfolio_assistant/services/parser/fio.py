import asyncio
import csv
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


class FioPortfolioParser(BasePortfolioParser):
    def __init__(self, isin_resolver: YahooISINResolver | None = None) -> None:
        self.isin_resolver = isin_resolver or YahooISINResolver()

    @property
    def broker_name(self) -> str:
        return "FIO e-Broker"

    def parse_sync(self, file_content: bytes) -> ImportedPortfolio:
        return asyncio.run(self.parse_async_internal(file_content))

    async def parse_async_internal(self, file_content: bytes) -> ImportedPortfolio:
        decoded_content = file_content.decode("utf-8-sig")
        csv_file = StringIO(decoded_content)
        reader = csv.reader(csv_file, delimiter=";")

        try:
            headers = [header.strip() for header in next(reader)]
        except StopIteration:
            raise ValueError("FIO CSV file is empty.") from None

        header_map = self._map_headers(headers)

        required_headers = [
            "asset_name",
            "isin",
            "purchase_price",
            "quantity",
        ]
        if not all(key in header_map for key in required_headers):
            raise ValueError(
                f"Missing essential columns. Found: {list(header_map.keys())}"
            )

        positions: list[StockPosition] = []
        for row in reader:
            if not row or all(not cell.strip() for cell in row):
                continue

            row_data = dict(zip(headers, row, strict=False))

            # Skip summary rows (e.g., "Součet (CZK)")
            first_col = row[0].strip() if row else ""
            if "Součet" in first_col:
                continue

            try:
                isin_or_symbol = row_data[header_map["isin"]].strip()
                asset_name = row_data[header_map["asset_name"]].strip()
                quantity = self._clean_decimal(row_data[header_map["quantity"]])
                purchase_price = self._clean_decimal(
                    row_data[header_map["purchase_price"]]
                )

                # Currency handling
                if "currency" in header_map:
                    currency_raw = row_data[header_map["currency"]].strip().upper()
                    if currency_raw == "0" or not currency_raw:
                        currency = Currency.CZK
                    else:
                        try:
                            currency = Currency(currency_raw)
                        except ValueError:
                            currency = Currency.CZK
                else:
                    currency = Currency.CZK

                # If the 'isin' column actually contains 'CZK', it's cash, skip it
                if isin_or_symbol == "CZK":
                    continue

                if quantity <= 0:
                    continue

                # For Fio, the 'isin' column might be a ticker or an ISIN
                ticker = await self.isin_resolver.resolve(isin_or_symbol)

                positions.append(
                    StockPosition(
                        ticker=ticker,
                        name=asset_name,
                        quantity=quantity,
                        average_price=purchase_price,
                        currency=currency,
                    )
                )
            except Exception as e:
                print(f"Skipping row due to parsing error: {row}. Error: {e}")
                continue

        return ImportedPortfolio(
            broker_name=self.broker_name,
            imported_at=datetime.now(),
            positions=positions,
        )

    def _map_headers(self, headers: list[str]) -> dict[str, str]:
        header_map = {}
        for header in headers:
            normalized_header = header.strip().lower()
            if normalized_header in [
                "název cenného papíru",
                "název cenného papíru (czk)",
                "symbol",
            ]:
                header_map["asset_name"] = header
                if normalized_header == "symbol":
                    header_map["isin"] = header
            elif normalized_header == "isin":
                header_map["isin"] = header
            elif normalized_header in ["kurz", "pořizovací kurz"]:
                header_map["purchase_price"] = header
            elif normalized_header in ["ks", "množství", "kusy"]:
                header_map["quantity"] = header
            elif normalized_header in ["měna", "akcie"]:
                header_map["currency"] = header
        return header_map

    def _clean_decimal(self, value: str) -> Decimal:
        cleaned_value = value.replace(",", ".").replace(" ", "")
        return Decimal(cleaned_value)
