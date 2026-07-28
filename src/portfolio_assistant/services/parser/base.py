"""Base portfolio parser interface.

This module defines the abstract base class for portfolio parsers.
"""

import asyncio
from abc import ABC, abstractmethod

from portfolio_assistant.models.portfolio import ImportedPortfolio


class BasePortfolioParser(ABC):
    """Abstract base class for importing portfolios from different brokers."""

    @property
    @abstractmethod
    def broker_name(self) -> str:
        """Returns the name of the broker.

        Returns:
            str: The broker's name.
        """
        pass

    @abstractmethod
    def parse_sync(self, file_content: bytes) -> ImportedPortfolio:
        """Synchronously parses broker-exported file content into an ImportedPortfolio.

        Args:
            file_content (bytes): The raw file bytes to parse.

        Returns:
            ImportedPortfolio: The parsed and validated portfolio data.

        Raises:
            Exception: If parsing fails due to invalid format or structure.
        """
        pass

    async def parse_async(self, file_content: bytes) -> ImportedPortfolio:
        """Asynchronously parses broker-exported file content.

        Executes the synchronous `parse_sync` method in a separate thread pool using
        `asyncio.to_thread` to prevent blocking the async event loop during CPU-bound
        parsing operations.

        Args:
            file_content (bytes): The raw file bytes to parse.

        Returns:
            ImportedPortfolio: The parsed and validated portfolio data.
        """
        return await asyncio.to_thread(self.parse_sync, file_content)
