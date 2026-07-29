"""Abstract base class for the valuation service."""

from abc import ABC, abstractmethod

from portfolio_assistant.models.portfolio import Currency, ImportedPortfolio
from portfolio_assistant.models.valuation import ValuedPortfolio


class BaseValuationService(ABC):
    """Abstract base class for valuing portfolios."""

    @abstractmethod
    async def value_portfolio_async(
        self,
        portfolio: ImportedPortfolio,
        target_currency: Currency = Currency.CZK,
    ) -> ValuedPortfolio:
        """Calculate the current value and weights of all positions in the portfolio.

        Args:
            portfolio: The imported portfolio with positions.
            target_currency: The currency in which the portfolio should be valued.

        Returns:
            ValuedPortfolio: The portfolio with current valuations and weights.

        Raises:
            ValuationError: If price or exchange rate fetching fails.
        """
