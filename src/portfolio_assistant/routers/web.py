"""Web routes for the portfolio dashboard."""

import json
import logging
from decimal import Decimal
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from portfolio_assistant.models.portfolio import Currency
from portfolio_assistant.models.user import User
from portfolio_assistant.services.ai.gemini import GeminiAIService
from portfolio_assistant.services.market_data.yfinance import (
    YFinanceMarketDataService,
)
from portfolio_assistant.services.parser.degiro import DegiroPortfolioParser
from portfolio_assistant.services.parser.fio_broker import (
    FioBrokerPortfolioParser,
)
from portfolio_assistant.services.portfolio_merger import PortfolioMerger
from portfolio_assistant.services.valuation.engine import ValuationService

from ..core.database import get_db_session
from ..dependencies import get_current_user, get_optional_current_user
from ..models.db_models import Portfolio, Position

logger = logging.getLogger(__name__)


def format_currency(value: Decimal) -> str:
    """Format currency value with proper grouping and decimal separator."""
    if value == Decimal(0):
        return "0.00"

    is_negative = value < 0
    abs_value = abs(value)

    # Convert absolute value to string and split into parts
    value_str = f"{abs_value:.2f}"
    integer_part, decimal_part = value_str.split(".")

    # Add thousand separators to the integer part
    formatted_integer = ""
    for i, char in enumerate(reversed(integer_part)):
        if i > 0 and i % 3 == 0:
            formatted_integer = " " + formatted_integer
        formatted_integer = char + formatted_integer

    sign = "-" if is_negative else ""
    return f"{sign}{formatted_integer},{decimal_part}"


# Set up templates
BASE_DIR = Path(__file__).parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Register custom Jinja2 filter
templates.env.filters["format_currency"] = format_currency

# Create router
router = APIRouter(prefix="", tags=["web"])


@router.post("/portfolios")
async def create_portfolio_web(
    name: Annotated[str, Form()],
    broker: Annotated[str, Form()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> RedirectResponse:
    """Create a new portfolio from the web form and redirect back to dashboard."""
    try:
        db_portfolio = Portfolio(
            name=name.strip(),
            broker=broker.strip(),
            user_id=current_user.id,
        )
        db.add(db_portfolio)
        db.commit()
        return RedirectResponse("/", status_code=303)
    except Exception as e:
        logger.exception("Failed to create portfolio via web form")
        raise HTTPException(status_code=500, detail="Failed to create portfolio") from e


# Initialize services using FastAPI dependency injection
def get_market_data_service() -> YFinanceMarketDataService:
    """FastAPI dependency: Get market data service instance."""
    return YFinanceMarketDataService()


def get_valuation_service(
    market_data_service: Annotated[
        YFinanceMarketDataService, Depends(get_market_data_service)
    ],
) -> ValuationService:
    """FastAPI dependency: Get valuation service instance."""
    return ValuationService(market_data_service)


def get_gemini_service() -> GeminiAIService:
    """FastAPI dependency: Get Gemini AI service instance."""
    return GeminiAIService()


def get_portfolio_parser() -> DegiroPortfolioParser:
    """FastAPI dependency: Get portfolio parser instance."""
    return DegiroPortfolioParser()


def get_fio_parser() -> FioBrokerPortfolioParser:
    """FastAPI dependency: Get Fio e-Broker parser instance."""
    return FioBrokerPortfolioParser()


def get_portfolio_merger() -> PortfolioMerger:
    """FastAPI dependency: Get portfolio merger instance."""
    return PortfolioMerger()


@router.get("/", response_class=HTMLResponse)
async def dashboard_get(
    request: Request,
    valuation_service: Annotated[ValuationService, Depends(get_valuation_service)],
    gemini_service: Annotated[GeminiAIService, Depends(get_gemini_service)],
    portfolio_merger: Annotated[PortfolioMerger, Depends(get_portfolio_merger)],
    db: Annotated[Session, Depends(get_db_session)],
    portfolio_id: int | None = None,
    current_user: Annotated[User | None, Depends(get_optional_current_user)] = None,
) -> HTMLResponse:
    """Render the dashboard with upload form or existing portfolio analysis."""
    valued_portfolio = None
    total_value_formatted = None
    chart_data_json = None
    ai_analysis_markdown = ""
    error = None
    portfolios: list[Portfolio] = []

    if current_user:
        try:
            from datetime import datetime

            from portfolio_assistant.models.portfolio import (
                ImportedPortfolio,
                StockPosition,
            )

            # Fetch all user portfolios
            statement_all = select(Portfolio).where(
                Portfolio.user_id == current_user.id
            )
            portfolios = list(db.exec(statement_all).all())

            # Filter logic
            db_portfolios_to_process = []
            if portfolio_id is not None:
                statement = select(Portfolio).where(
                    Portfolio.id == portfolio_id,
                    Portfolio.user_id == current_user.id,
                )
                p_selected = db.exec(statement).first()
                if p_selected:
                    db_portfolios_to_process = [p_selected]
            else:
                db_portfolios_to_process = portfolios

            # Gather positions
            imported_portfolios = []
            for db_p in db_portfolios_to_process:
                if db_p.positions:
                    positions = []
                    for p in db_p.positions:
                        positions.append(
                            StockPosition(
                                ticker=p.ticker,
                                name=p.asset_name,
                                quantity=p.quantity,
                                average_price=p.unit_cost,
                                currency=Currency(p.currency),
                            )
                        )
                    imported_portfolios.append(
                        ImportedPortfolio(
                            broker_name=db_p.name,
                            imported_at=datetime.now(),
                            positions=positions,
                        )
                    )

            if imported_portfolios:
                # Merge if multiple
                if len(imported_portfolios) == 1:
                    final_portfolio = imported_portfolios[0]
                else:
                    final_portfolio = portfolio_merger.merge_portfolios(
                        imported_portfolios
                    )

                # Value the portfolio
                valued_portfolio = await valuation_service.value_portfolio_async(
                    final_portfolio, target_currency=Currency.CZK
                )

                # Generate AI analysis
                anonymized_portfolio = valued_portfolio.to_anonymized()
                ai_analysis_markdown = await gemini_service.analyze_portfolio(
                    anonymized_portfolio
                )

                # Prepare chart data
                chart_labels = [pos.ticker for pos in valued_portfolio.positions]
                chart_weights = [
                    float(pos.weight * 100) for pos in valued_portfolio.positions
                ]
                chart_data = {"labels": chart_labels, "weights": chart_weights}
                chart_data_json = json.dumps(chart_data)

                # Format total value
                total_value_formatted = format_currency(valued_portfolio.total_value)

        except SQLAlchemyError:
            logger.exception("Database error while loading portfolio for dashboard")
            error = "Database persistence failed."
        except Exception:
            logger.exception("Unexpected error while loading portfolio for dashboard")
            error = "An unexpected error occurred."

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "valued_portfolio": valued_portfolio,
            "total_value_formatted": total_value_formatted,
            "chart_data_json": chart_data_json,
            "error": error,
            "username": current_user.email if current_user else None,
            "ai_analysis_markdown": ai_analysis_markdown,
            "portfolios": portfolios,
            "selected_portfolio_id": portfolio_id,
        },
    )


@router.post("/upload", response_class=HTMLResponse)
async def upload_portfolio(
    request: Request,
    valuation_service: Annotated[ValuationService, Depends(get_valuation_service)],
    degiro_parser: Annotated[DegiroPortfolioParser, Depends(get_portfolio_parser)],
    fio_parser: Annotated[FioBrokerPortfolioParser, Depends(get_fio_parser)],
    portfolio_merger: Annotated[PortfolioMerger, Depends(get_portfolio_merger)],
    gemini_service: Annotated[GeminiAIService, Depends(get_gemini_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
    portfolio_id: Annotated[int, Form()],
    degiro_file: Annotated[UploadFile | None, Form()] = None,
    fio_file: Annotated[UploadFile | None, Form()] = None,
) -> HTMLResponse:
    """Handle portfolio CSV upload and display valuation results."""
    try:
        imported_portfolios = []
        portfolios: list[Portfolio] = []

        # Fetch all user portfolios for rendering context
        statement_all = select(Portfolio).where(Portfolio.user_id == current_user.id)
        portfolios = list(db.exec(statement_all).all())

        if not degiro_file and not fio_file:
            raise HTTPException(
                status_code=400, detail="At least one portfolio file must be provided."
            )

        # Parse DEGIRO file if provided
        if degiro_file:
            degiro_content = await degiro_file.read()
            degiro_portfolio = await degiro_parser.parse(degiro_content)
            imported_portfolios.append(degiro_portfolio)

        # Parse Fio e-Broker file if provided
        if fio_file:
            fio_content = await fio_file.read()
            fio_portfolio = await fio_parser.parse(fio_content)
            imported_portfolios.append(fio_portfolio)

        # If only one portfolio is uploaded, no merge is needed.
        if len(imported_portfolios) == 1:
            final_portfolio = imported_portfolios[0]
        elif len(imported_portfolios) > 1:
            final_portfolio = portfolio_merger.merge_portfolios(imported_portfolios)
        else:
            raise ValueError("No portfolio data to process after parsing.")

        # Save or update Positions in DB for the specified portfolio
        from datetime import date

        try:
            # Verify the portfolio belongs to user
            verify_stmt = select(Portfolio).where(
                Portfolio.id == portfolio_id,
                Portfolio.user_id == current_user.id,
            )
            db_portfolio = db.exec(verify_stmt).first()
            if not db_portfolio:
                raise HTTPException(status_code=404, detail="Portfolio not found.")

            # Clear old positions for this portfolio only
            for pos in db_portfolio.positions:
                db.delete(pos)
            db.flush()

            # Create Positions
            for stock_pos in final_portfolio.positions:
                db_pos = Position(
                    asset_name=stock_pos.name or f"Asset {stock_pos.ticker}",
                    ticker=stock_pos.ticker,
                    isin=None,
                    currency=stock_pos.currency.value,
                    quantity=stock_pos.quantity,
                    unit_cost=stock_pos.average_price,
                    acquisition_date=date.today(),
                    portfolio_id=db_portfolio.id,
                )
                db.add(db_pos)

            db.commit()
            db.refresh(db_portfolio)
        except SQLAlchemyError:
            db.rollback()
            logger.exception("Database error during portfolio upload")
            raise HTTPException(
                status_code=500, detail="Database persistence failed."
            ) from None
        except Exception as e:
            db.rollback()
            if isinstance(e, HTTPException):
                raise e
            logger.exception("Unexpected error during portfolio upload")
            raise HTTPException(
                status_code=500, detail="An unexpected error occurred."
            ) from None

        # Value the portfolio
        valued_portfolio = await valuation_service.value_portfolio_async(
            final_portfolio, target_currency=Currency.CZK
        )

        # Generate AI analysis
        anonymized_portfolio = valued_portfolio.to_anonymized()
        ai_analysis_markdown = await gemini_service.analyze_portfolio(
            anonymized_portfolio
        )

        # Prepare chart data
        chart_labels = [pos.ticker for pos in valued_portfolio.positions]
        chart_weights = [float(pos.weight * 100) for pos in valued_portfolio.positions]

        chart_data = {
            "labels": chart_labels,
            "weights": chart_weights,
        }

        # Convert chart data to JSON string for safe template rendering
        chart_data_json = json.dumps(chart_data)

        # Format total value
        total_value_formatted = format_currency(valued_portfolio.total_value)

        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "valued_portfolio": valued_portfolio,
                "total_value_formatted": total_value_formatted,
                "chart_data_json": chart_data_json,
                "error": None,
                "username": current_user.email if current_user else None,
                "ai_analysis_markdown": ai_analysis_markdown,
                "portfolios": portfolios,
                "selected_portfolio_id": portfolio_id,
            },
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception("Failed to process portfolio upload")

        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "valued_portfolio": None,
                "total_value_formatted": None,
                "chart_data_json": None,
                "error": f"Error processing portfolio: {str(e)}",
                "username": current_user.email if current_user else None,
                "portfolios": portfolios,
                "selected_portfolio_id": portfolio_id,
            },
        )
