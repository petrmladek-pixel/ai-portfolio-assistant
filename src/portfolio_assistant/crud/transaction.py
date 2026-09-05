"""Database operations for portfolio transactions.

This module provides CRUD functions for managing transaction data
using SQLModel for database operations.
"""

from collections.abc import Sequence

from sqlmodel import Session, select

from portfolio_assistant.models.db_models import Transaction


def get_portfolio_transactions(
    session: Session, portfolio_id: int
) -> Sequence[Transaction]:
    """Retrieve all transactions for a given portfolio.

    Args:
        session (Session): The database session.
        portfolio_id (int): The ID of the portfolio to fetch transactions for.

    Returns:
        Sequence[Transaction]: A sequence of Transaction objects for the
            portfolio.
    """
    statement = select(Transaction).where(Transaction.portfolio_id == portfolio_id)
    return session.exec(statement).all()
