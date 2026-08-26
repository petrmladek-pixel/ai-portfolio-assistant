"""HTTP-independent workflows for portfolio persistence."""

from datetime import date
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from portfolio_assistant.core.exceptions import (
    InvalidImportTypeError,
    PersistenceError,
    PortfolioImportError,
    PortfolioNotFoundError,
)
from portfolio_assistant.crud import portfolio as portfolio_crud
from portfolio_assistant.models.db_models import Portfolio, Position
from portfolio_assistant.models.portfolio import ImportedPortfolio
from portfolio_assistant.services.parser.base import BasePortfolioParser
from portfolio_assistant.services.parser.degiro import DegiroPortfolioParser
from portfolio_assistant.services.parser.fio_broker import FioBrokerPortfolioParser


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

    def ensure_default_portfolio(self, session: Session, user_id: int) -> Portfolio:
        """Return a user's first portfolio, creating the default when absent."""
        portfolio = portfolio_crud.get_first_portfolio_for_user(session, user_id)
        if portfolio is not None:
            return portfolio
        return self.create(session, "Default Portfolio", "Default", user_id)

    async def import_portfolio_file(
        self,
        session: Session,
        user_id: int,
        portfolio_id: int,
        import_type: str,
        file_content: bytes,
        degiro_parser: DegiroPortfolioParser,
        fio_parser: FioBrokerPortfolioParser,
    ) -> ImportedPortfolio:
        """Parse one broker file and replace positions in its target portfolio."""
        parser = self._select_parser(import_type, degiro_parser, fio_parser)
        try:
            imported = await parser.parse(file_content)
        except Exception as error:
            raise PortfolioImportError(str(error)) from error
        self.replace_imported_positions(session, user_id, portfolio_id, imported)
        return imported

    def _select_parser(
        self,
        import_type: str,
        degiro_parser: DegiroPortfolioParser,
        fio_parser: FioBrokerPortfolioParser,
    ) -> BasePortfolioParser:
        """Return the parser associated with a normalized import type."""
        parsers = {"degiro": degiro_parser, "fio": fio_parser}
        try:
            return parsers[import_type.strip().lower()]
        except KeyError as error:
            raise InvalidImportTypeError from error

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

    async def process_portfolio_import(
        self,
        session: Session,
        user_id: int,
        portfolio_id: int,
        import_type: str,
        file: Any,
    ) -> ImportedPortfolio:
        """Process portfolio import from file upload or bytes."""
        if hasattr(file, "read"):
            content = await file.read() if callable(file.read) else file.read()
        elif isinstance(file, bytes):
            content = file
        else:
            content = bytes(file)

        degiro_parser = DegiroPortfolioParser()
        fio_parser = FioBrokerPortfolioParser()
        return await self.import_portfolio_file(
            session,
            user_id,
            portfolio_id,
            import_type,
            content,
            degiro_parser,
            fio_parser,
        )
