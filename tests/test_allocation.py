"""Tests for portfolio allocation calculations."""

from decimal import Decimal
from unittest.mock import patch

from portfolio_assistant.models.db_models import Transaction
from portfolio_assistant.models.portfolio import TransactionType
from portfolio_assistant.services.allocation import AllocationService


def test_calculate_portfolio_allocations() -> None:
    """Calculate net holdings, values, and allocation percentages."""
    transactions = [
        Transaction(
            ticker="AAPL",
            quantity=Decimal("5"),
            transaction_type=TransactionType.BUY,
            portfolio_id=4,
        ),
        Transaction(
            ticker="AAPL",
            quantity=Decimal("2"),
            transaction_type=TransactionType.SELL,
            portfolio_id=4,
        ),
        Transaction(
            ticker="MSFT",
            quantity=Decimal("1"),
            transaction_type=TransactionType.BUY,
            portfolio_id=4,
        ),
    ]

    with patch(
        "portfolio_assistant.services.allocation."
        "transaction_crud.get_portfolio_transactions",
        return_value=transactions,
    ):
        response = AllocationService().calculate_portfolio_allocations(
            session=None,  # type: ignore[arg-type]
            portfolio_id=4,
            current_prices={"AAPL": Decimal("100"), "MSFT": Decimal("200")},
        )

    assert response.total_value == Decimal("500")
    assert response.allocations[0].ticker == "AAPL"
    assert response.allocations[0].quantity == Decimal("3")
    assert response.allocations[0].percentage == Decimal("60")
    assert response.allocations[1].percentage == Decimal("40")


def test_calculate_portfolio_allocations_returns_empty_for_zero_value() -> None:
    """Return no allocations when a portfolio has no positive-valued holdings."""
    with patch(
        "portfolio_assistant.services.allocation."
        "transaction_crud.get_portfolio_transactions",
        return_value=[],
    ):
        response = AllocationService().calculate_portfolio_allocations(
            session=None,  # type: ignore[arg-type]
            portfolio_id=4,
            current_prices={},
        )

    assert response.total_value == Decimal("0.00")
    assert response.allocations == []
