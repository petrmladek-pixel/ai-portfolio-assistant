"""HTTP-independent workflows for portfolio persistence."""

from datetime import date

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from portfolio_assistant.core.exceptions import PersistenceError, PortfolioNotFoundError
from portfolio_assistant.crud import portfolio as portfolio_crud
from portfolio_assistant.models.db_models import Portfolio, Position
from portfolio_assistant.models.portfolio import ImportedPortfolio


class PortfolioService:
    """Coordinate persistence workflows for portfolios."""

    def create(
        self, session: Session, name: str, broker: str, user_id: int
    ) -> Portfolio:
        """Create a portfolio for a user."""
        portfolio = Portfolio(name=name, broker=broker, user_id=user_id)
        try:
            return portfolio_crud.create_portfolio(session, portfolio)
        except SQLAlchemyError as error:
            session.rollback()
            raise PersistenceError from error

    def replace_imported_positions(
        self,
        session: Session,
        user_id: int,
        portfolio_id: int,
        imported_portfolio: ImportedPortfolio,
    ) -> Portfolio:
        """Replace a user's portfolio positions with an imported portfolio."""
        portfolio = portfolio_crud.get_portfolio_for_user(
            session, portfolio_id, user_id
        )
        if portfolio is None:
            raise PortfolioNotFoundError
        positions = [
            Position(
                asset_name=position.name or f"Asset {position.ticker}",
                ticker=position.ticker,
                currency=position.currency.value,
                quantity=position.quantity,
                unit_cost=position.average_price,
                acquisition_date=date.today(),
                portfolio_id=portfolio.id,
            )
            for position in imported_portfolio.positions
        ]
        try:
            return portfolio_crud.replace_positions(session, portfolio, positions)
        except SQLAlchemyError as error:
            session.rollback()
            raise PersistenceError from error
