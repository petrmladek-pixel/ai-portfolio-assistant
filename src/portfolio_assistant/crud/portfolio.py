"""Database operations for portfolios and their positions."""

from collections.abc import Sequence

from sqlmodel import Session, col, select

from portfolio_assistant.models.db_models import Portfolio, Position


def create_portfolio(session: Session, portfolio: Portfolio) -> Portfolio:
    """Persist and refresh a portfolio."""
    session.add(portfolio)
    session.commit()
    session.refresh(portfolio)
    return portfolio


def create_portfolio_with_positions(
    session: Session,
    portfolio: Portfolio,
    positions: Sequence[Position],
) -> Portfolio:
    """Persist a portfolio and its positions in one database transaction."""
    session.add(portfolio)
    session.flush()
    if portfolio.id is None:
        raise RuntimeError("Portfolio was not assigned an identifier.")
    for position in positions:
        position.portfolio_id = portfolio.id
        session.add(position)
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


def get_portfolio_by_name_for_user(
    session: Session,
    user_id: int,
    name: str,
) -> Portfolio | None:
    """Return a user's portfolio with the exact supplied name, if present."""
    statement = select(Portfolio).where(
        Portfolio.user_id == user_id,
        Portfolio.name == name,
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


def get_demo_portfolio(session: Session, name: str) -> Portfolio | None:
    """Return the public portfolio owned by the system demo user."""
    from portfolio_assistant.models.user import User

    statement = (
        select(Portfolio)
        .join(User)
        .where(col(User.is_demo).is_(True), Portfolio.name == name)
    )
    return session.exec(statement).first()


def replace_positions(
    session: Session, portfolio: Portfolio, positions: Sequence[Position]
) -> Portfolio:
    """Replace all positions for a portfolio in one transaction."""
    if portfolio.id is None:
        raise RuntimeError("Portfolio must have an identifier before replacement.")
    for position in portfolio.positions:
        session.delete(position)
    session.flush()
    for position in positions:
        position.portfolio_id = portfolio.id
        session.add(position)
    session.commit()
    session.refresh(portfolio)
    return portfolio
