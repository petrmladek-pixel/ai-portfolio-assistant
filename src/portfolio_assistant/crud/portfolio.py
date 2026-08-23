"""Database operations for portfolios and their positions."""

from collections.abc import Sequence

from sqlmodel import Session, select

from portfolio_assistant.models.db_models import Portfolio, Position


def create_portfolio(session: Session, portfolio: Portfolio) -> Portfolio:
    """Persist and refresh a portfolio."""
    session.add(portfolio)
    session.commit()
    session.refresh(portfolio)
    return portfolio


def get_portfolio_for_user(
    session: Session, portfolio_id: int, user_id: int
) -> Portfolio | None:
    """Return a portfolio only when it belongs to the supplied user."""
    statement = select(Portfolio).where(
        Portfolio.id == portfolio_id,
        Portfolio.user_id == user_id,
    )
    return session.exec(statement).first()


def get_first_portfolio_for_user(session: Session, user_id: int) -> Portfolio | None:
    """Return the first portfolio owned by a user."""
    statement = select(Portfolio).where(Portfolio.user_id == user_id)
    return session.exec(statement).first()


def get_portfolios_for_user(session: Session, user_id: int) -> Sequence[Portfolio]:
    """Return all portfolios owned by a user."""
    statement = select(Portfolio).where(Portfolio.user_id == user_id)
    return session.exec(statement).all()


def replace_positions(
    session: Session, portfolio: Portfolio, positions: Sequence[Position]
) -> Portfolio:
    """Replace all positions for a portfolio in one transaction."""
    for position in portfolio.positions:
        session.delete(position)
    session.flush()
    for position in positions:
        session.add(position)
    session.commit()
    session.refresh(portfolio)
    return portfolio
