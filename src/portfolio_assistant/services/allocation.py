"""Allocation calculation service for portfolio management.

This module provides stateless calculation logic for determining portfolio
asset allocations based on transaction history and current market prices.
"""

from decimal import Decimal
from typing import TypedDict

from sqlmodel import Session

from portfolio_assistant.crud import transaction as transaction_crud
from portfolio_assistant.models.allocation import (
    AssetAllocation,
    PortfolioAllocationResponse,
)
from portfolio_assistant.models.portfolio import TransactionType


class _AllocationDraft(TypedDict):
    """Intermediate allocation values before percentage calculation."""

    ticker: str
    quantity: Decimal
    current_price: Decimal
    market_value: Decimal


class AllocationService:
    """Service for calculating portfolio allocations from transaction data."""

    def calculate_portfolio_allocations(
        self,
        session: Session,
        portfolio_id: int,
        current_prices: dict[str, Decimal],
    ) -> PortfolioAllocationResponse:
        """Calculate asset allocations for a portfolio.

        Args:
            session (Session): The database session.
            portfolio_id (int): The ID of the portfolio to analyze.
            current_prices (dict[str, Decimal]): Mapping of ticker symbols to
                current market prices.

        Returns:
            PortfolioAllocationResponse: The calculated allocation data.
        """
        transactions = transaction_crud.get_portfolio_transactions(
            session, portfolio_id
        )

        net_quantities: dict[str, Decimal] = {}
        for txn in transactions:
            if txn.transaction_type == TransactionType.BUY:
                net_quantities[txn.ticker] = (
                    net_quantities.get(txn.ticker, Decimal("0")) + txn.quantity
                )
            elif txn.transaction_type == TransactionType.SELL:
                net_quantities[txn.ticker] = (
                    net_quantities.get(txn.ticker, Decimal("0")) - txn.quantity
                )

        filtered_assets = {
            ticker: quantity
            for ticker, quantity in net_quantities.items()
            if quantity > 0
        }

        allocations: list[_AllocationDraft] = []
        total_value = Decimal("0.00")
        for ticker, quantity in filtered_assets.items():
            current_price = current_prices.get(ticker, Decimal("0.00"))
            market_value = quantity * current_price
            allocations.append(
                {
                    "ticker": ticker,
                    "quantity": quantity,
                    "current_price": current_price,
                    "market_value": market_value,
                }
            )
            total_value += market_value

        if total_value == 0:
            return PortfolioAllocationResponse(
                portfolio_id=portfolio_id,
                total_value=Decimal("0.00"),
                allocations=[],
            )

        final_allocations: list[AssetAllocation] = []
        for alloc in allocations:
            percentage = (alloc["market_value"] / total_value) * 100
            final_allocations.append(
                AssetAllocation(
                    ticker=alloc["ticker"],
                    quantity=alloc["quantity"],
                    current_price=alloc["current_price"],
                    market_value=alloc["market_value"],
                    percentage=percentage,
                )
            )

        return PortfolioAllocationResponse(
            portfolio_id=portfolio_id,
            total_value=total_value,
            allocations=final_allocations,
        )
