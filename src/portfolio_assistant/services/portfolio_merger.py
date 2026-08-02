from collections import defaultdict
from decimal import Decimal

from portfolio_assistant.models.portfolio import (
    Currency,
    ImportedPortfolio,
    ParsedPosition,
)


class PortfolioMerger:
    """Merges multiple ImportedPortfolios into a single, unified portfolio of
    ParsedPositions.

    The merger aggregates positions for the same ticker across different brokers,
    calculates a weighted average price, and determines total value and weight.
    All calculations are performed using CZK as the base currency. For simplicity
    in this sprint, currency conversion is assumed or handled externally.
    """

    def merge_portfolios(
        self, portfolios: list[ImportedPortfolio]
    ) -> list[ParsedPosition]:
        """Merges a list of imported portfolios into a single list of ParsedPositions.

        Args:
            portfolios (List[ImportedPortfolio]): A list of portfolios to merge.

        Returns:
            List[ParsedPosition]: A list of unified and calculated portfolio positions.
        """
        aggregated_positions: dict[str, dict[str, Decimal | str | list[Currency]]] = (
            defaultdict(
                lambda: {
                    "total_quantity": Decimal(0),
                    "total_cost_czk": Decimal(0),
                    "name": "",
                    "currencies": [],
                }
            )
        )

        for portfolio in portfolios:
            for position in portfolio.positions:
                ticker = position.ticker
                # For simplicity, assuming all positions are converted to CZK for merger
                # In a real scenario, this would involve exchange rates.
                if position.currency != Currency.CZK:
                    # Placeholder for actual conversion. For now, we\"ll treat non-CZK
                    # as if they were CZK for calculation purposes or raise an error
                    # depending on strictness.
                    # For this task, we assume conversion is already done or implicitly
                    # handled for price calculations.
                    pass

                # Aggregate quantity and total cost
                current_quantity: Decimal = Decimal(
                    str(aggregated_positions[ticker]["total_quantity"])
                )
                current_cost: Decimal = Decimal(
                    str(aggregated_positions[ticker]["total_cost_czk"])
                )
                current_name: str = str(aggregated_positions[ticker]["name"])
                current_currencies: list[Currency] = aggregated_positions[ticker][
                    "currencies"
                ]  # type: ignore

                aggregated_positions[ticker]["total_quantity"] = (
                    current_quantity + position.quantity
                )
                aggregated_positions[ticker]["total_cost_czk"] = current_cost + (
                    position.quantity * position.average_price
                )

                if not current_name:
                    aggregated_positions[ticker]["name"] = str(position.name)

                if position.currency not in current_currencies:
                    current_currencies.append(position.currency)

                # Re-assign the list to the dictionary to update the original reference
                # MyPy needs help understanding the `defaultdict` and complex nested
                # types.
                aggregated_positions[ticker]["currencies"] = current_currencies

        parsed_positions: list[ParsedPosition] = []
        total_portfolio_value_czk = Decimal(0)

        # First pass to calculate total portfolio value in CZK
        for _ticker, data in aggregated_positions.items():
            total_value_czk_for_ticker = Decimal(str(data["total_cost_czk"]))
            total_portfolio_value_czk += total_value_czk_for_ticker

        # Second pass to create ParsedPosition and calculate weights
        for ticker, data in aggregated_positions.items():
            total_quantity = Decimal(str(data["total_quantity"]))
            total_cost_czk = Decimal(str(data["total_cost_czk"]))
            asset_name = str(data["name"])
            currencies: list[Currency] = data["currencies"]  # type: ignore

            if total_quantity == Decimal(0):
                continue

            average_price_czk = total_cost_czk / total_quantity
            total_value_czk = total_cost_czk

            weight = (
                total_value_czk / total_portfolio_value_czk
                if total_portfolio_value_czk > 0
                else Decimal(0)
            )

            # Ensure consistent currency if multiple were found (e.g., from different
            # brokers for the same stock, which might imply a conversion issue or
            # a mixed portfolio that needs more complex handling).
            # For this task, we\"ll log a warning but proceed, assuming primary CZK
            # focus.
            if len(currencies) > 1:
                print(
                    f"Warning: Ticker {ticker} has multiple currencies specified: "
                    f"{currencies}. Using CZK for merged calculation."
                )

            parsed_positions.append(
                ParsedPosition(
                    ticker=ticker,
                    name=asset_name if asset_name else ticker,  # Fallback to ticker
                    quantity=total_quantity,
                    average_price_czk=average_price_czk,
                    total_value_czk=total_value_czk,
                    weight=weight,
                )
            )

        return parsed_positions
