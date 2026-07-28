"""Abstract base parser for portfolio files.

This module defines the base interface for all broker-specific portfolio parsers,
providing both synchronous and asynchronous parsing capabilities.
"""

import asyncio
from abc import ABC, abstractmethod

from portfolio_assistant.models.portfolio import ImportedPortfolio


class BasePortfolioParser(ABC):
    """Abstract base class for all portfolio parsers.

    Defines the contract for parsing portfolio files from different brokers
    into a standardized ImportedPortfolio model.
    """

    @property
    @abstractmethod
    def broker_name(self) -> str:
        """Return the name of the broker this parser handles.

        Returns:
            str: The name of the broker (e.g., 'Degiro', 'Revolut').
        """

    @abstractmethod
    def parse_sync(self, file_content: bytes) -> ImportedPortfolio:
        """Synchronously parse the content of a portfolio file.

        This method should implement the actual parsing logic, which is often
        CPU-bound (e.g., CSV parsing, PDF extraction, data validation).

        Args:
            file_content (bytes): The raw binary content of the portfolio file.

        Returns:
            ImportedPortfolio: The parsed and validated portfolio data.

        Raises:
            NotImplementedError: If the subclass does not implement this method.
        """

    async def parse_async(self, file_content: bytes) -> ImportedPortfolio:
        """Asynchronously parse the content of a portfolio file.

        This method executes the synchronous `parse_sync` method in a separate
        thread pool using `asyncio.to_thread` to prevent blocking the async
        event loop during CPU-bound parsing operations.

        Args:
            file_content (bytes): The raw binary content of the portfolio file.

        Returns:
            ImportedPortfolio: The parsed and validated portfolio data.
        """
        return await asyncio.to_thread(self.parse_sync, file_content)
