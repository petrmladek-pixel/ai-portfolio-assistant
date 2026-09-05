"""Implementation of the valuation service."""

from decimal import Decimal
from typing import Any

from portfolio_assistant.core.utils import get_now_utc
from portfolio_assistant.exceptions.valuation import ValuationError
from portfolio_assistant.models.portfolio import Currency, ImportedPortfolio
from portfolio_assistant.models.valuation import ValuedPortfolio, ValuedPosition
from portfolio_assistant.services.market_data.base import BaseMarketDataService
from portfolio_assistant.services.valuation.base import BaseValuationService


class ValuationService(BaseValuationService):
    """Service for valuing portfolios using market data."""

    def __init__(self, market_data_service: BaseMarketDataService):
        """Initializes the valuation service.

        Args:
            market_data_service: Service for fetching market prices and exchange rates.
        """
        self._market_data_service = market_data_service

    async def value_portfolio_async(
        self,
        portfolio: ImportedPortfolio,
        target_currency: Currency = Currency.CZK,
        db_session: Any = None,
    ) -> ValuedPortfolio:
        """Calculate the current value and weights of all positions in the portfolio.

        Args:
            portfolio: The imported portfolio with positions.
            target_currency: The currency in which the portfolio should be valued.
            db_session: Optional database session for price caching.

        Returns:
            ValuedPortfolio: The portfolio with current valuations and weights.

        Raises:
            ValuationError: If price or exchange rate fetching fails.
        """
        if not portfolio.positions:
            return ValuedPortfolio(
                broker_name=portfolio.broker_name,
                imported_at=portfolio.imported_at,
                valued_at=get_now_utc(),
                positions=[],
                total_value=Decimal("0"),
                target_currency=target_currency,
            )

        tickers = sorted(list({pos.ticker for pos in portfolio.positions}))

        try:
            prices = await self._market_data_service.get_current_prices(
                tickers, db_session
            )
        except Exception as e:
            raise ValuationError(f"Failed to fetch market prices: {e}") from e

        # Validate that we have prices for all tickers
        for ticker in tickers:
            if ticker not in prices or prices[ticker] is None or prices[ticker] <= 0:
                raise ValuationError(f"Missing or invalid price for ticker: {ticker}")

        # Fetch required exchange rates
        exchange_rates: dict[Currency, Decimal] = {target_currency: Decimal("1.0")}
        # Sort for consistent test mocking
        required_currencies = sorted(
            list({pos.currency for pos in portfolio.positions}),
            key=lambda c: c.value,
        )

        for curr in required_currencies:
            if curr not in exchange_rates:
                try:
                    rate = await self._market_data_service.get_exchange_rate(
                        from_currency=curr, to_currency=target_currency
                    )
                    exchange_rates[curr] = rate
                except Exception as e:
                    raise ValuationError(
                        f"Failed to fetch exchange rate {curr} -> "
                        f"{target_currency}: {e}"
                    ) from e

        valued_positions: list[ValuedPosition] = []
        total_value = Decimal("0")

        # First pass: calculate individual values
        for pos in portfolio.positions:
            unit_price_original = prices[pos.ticker]
            rate = exchange_rates[pos.currency]
            unit_price_target = unit_price_original * rate
            total_value_target = pos.quantity * unit_price_target

            total_value += total_value_target

            valued_positions.append(
                ValuedPosition(
                    ticker=pos.ticker,
                    name=pos.name,
                    quantity=pos.quantity,
                    unit_price_original=unit_price_original,
                    currency_original=pos.currency,
                    unit_price_target=unit_price_target,
                    currency_target=target_currency,
                    total_value_target=total_value_target,
                    weight=Decimal("0"),  # Calculated in second pass
                )
            )

        # Sort positions by total_value_target descending for consistent ordering
        valued_positions.sort(key=lambda vp: vp.total_value_target, reverse=True)

        # Second pass: calculate weights
        if total_value > 0:
            for vp in valued_positions:
                vp.weight = vp.total_value_target / total_value

        return ValuedPortfolio(
            broker_name=portfolio.broker_name,
            imported_at=portfolio.imported_at,
            valued_at=get_now_utc(),
            positions=valued_positions,
            total_value=total_value,
            target_currency=target_currency,
        )
