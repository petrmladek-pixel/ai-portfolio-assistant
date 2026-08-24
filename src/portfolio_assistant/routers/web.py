"""Web router assembly and shared FastAPI dependencies."""

from decimal import Decimal
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from portfolio_assistant.models.user import User
from portfolio_assistant.services.ai.gemini import GeminiAIService
from portfolio_assistant.services.market_data.yfinance import YFinanceMarketDataService
from portfolio_assistant.services.parser.degiro import DegiroPortfolioParser
from portfolio_assistant.services.parser.fio_broker import FioBrokerPortfolioParser
from portfolio_assistant.services.portfolio_merger import PortfolioMerger
from portfolio_assistant.services.portfolio_service import PortfolioService
from portfolio_assistant.services.valuation.engine import ValuationService

from ..core.database import get_db_session
from ..core.exceptions import PersistenceError
from ..dependencies import get_current_user, get_persisted_user_id

BASE_DIR = Path(__file__).parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")
router = APIRouter(prefix="", tags=["web"])


def format_currency(value: Decimal) -> str:
    """Format currency using spaces for groups and a comma decimal separator."""
    if value == Decimal("0"):
        return "0.00"
    value_string = f"{abs(value):.2f}"
    integer_part, decimal_part = value_string.split(".")
    chunks = [
        integer_part[max(0, index - 3) : index]
        for index in range(len(integer_part), 0, -3)
    ]
    sign = "-" if value < 0 else ""
    return f"{sign}{' '.join(reversed(chunks))},{decimal_part}"


templates.env.filters["format_currency"] = format_currency


def get_market_data_service() -> YFinanceMarketDataService:
    """Provide the market data integration."""
    return YFinanceMarketDataService()


def get_valuation_service(
    market_data: Annotated[YFinanceMarketDataService, Depends(get_market_data_service)],
) -> ValuationService:
    """Provide the valuation service."""
    return ValuationService(market_data)


def get_gemini_service() -> GeminiAIService:
    """Provide the AI analysis integration."""
    return GeminiAIService()


def get_portfolio_parser() -> DegiroPortfolioParser:
    """Provide the DEGIRO parser."""
    return DegiroPortfolioParser()


def get_fio_parser() -> FioBrokerPortfolioParser:
    """Provide the Fio parser."""
    return FioBrokerPortfolioParser()


def get_portfolio_merger() -> PortfolioMerger:
    """Provide the portfolio merger."""
    return PortfolioMerger()


def get_portfolio_service() -> PortfolioService:
    """Provide the portfolio persistence service."""
    return PortfolioService()


@router.post("/portfolios")
async def create_portfolio_web(
    name: Annotated[str, Form()],
    broker: Annotated[str, Form()],
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service)],
) -> RedirectResponse:
    """Create a portfolio from a web form."""
    user_id = get_persisted_user_id(current_user)
    try:
        portfolio_service.create(session, name.strip(), broker.strip(), user_id)
    except PersistenceError:
        raise HTTPException(
            status_code=500, detail="Failed to create portfolio"
        ) from None
    return RedirectResponse("/", status_code=303)
