"""Web routes for the portfolio dashboard."""

import json
import logging
from decimal import Decimal
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from portfolio_assistant.models.portfolio import Currency
from portfolio_assistant.models.user import User
from portfolio_assistant.services.ai.gemini import GeminiAIService
from portfolio_assistant.services.market_data.yfinance import YFinanceMarketDataService
from portfolio_assistant.services.parser.degiro import DegiroPortfolioParser
from portfolio_assistant.services.parser.fio_broker import FioBrokerPortfolioParser
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
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User | None, Depends(get_optional_current_user)] = None,
) -> HTMLResponse:
    """Render the dashboard with upload form or existing portfolio analysis."""
    valued_portfolio = None
    total_value_formatted = None
    chart_data_json = None
    ai_analysis_markdown = ""
    error = None

    if current_user:
        try:
            from datetime import datetime

            from sqlmodel import select

            from portfolio_assistant.models.portfolio import (
                ImportedPortfolio,
                StockPosition,
            )

            # Try to load existing portfolio from DB
            statement = select(Portfolio).where(Portfolio.user_id == current_user.id)
            db_portfolio = db.exec(statement).first()

            if db_portfolio and db_portfolio.positions:
                # Convert DB models to ImportedPortfolio for valuation
                positions = []
                for p in db_portfolio.positions:
                    positions.append(
                        StockPosition(
                            ticker=p.ticker,
                            name=p.asset_name,
                            quantity=p.quantity,
                            average_price=p.unit_cost,
                            currency=Currency(p.currency),
                        )
                    )

                imported_portfolio = ImportedPortfolio(
                    broker_name=db_portfolio.name,
                    imported_at=datetime.now(),  # Use current time for valuation
                    positions=positions,
                )

                # Value the portfolio
                valued_portfolio = await valuation_service.value_portfolio_async(
                    imported_portfolio, target_currency=Currency.CZK
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
    degiro_file: Annotated[UploadFile | None, Form()] = None,
    fio_file: Annotated[UploadFile | None, Form()] = None,
) -> HTMLResponse:
    """Handle portfolio CSV upload and display valuation results."""
    try:
        imported_portfolios = []

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
            # This case should ideally be caught by the HTTPException above,
            # but added for completeness.
            raise ValueError("No portfolio data to process after parsing.")

        # Save or update Portfolio & Positions in DB for logged-in user
        from datetime import date

        from sqlmodel import select

        try:
            # Delete any existing portfolio and positions for user (upsert behavior)
            existing_stmt = select(Portfolio).where(
                Portfolio.user_id == current_user.id
            )
            existing_portfolios = db.exec(existing_stmt).all()
            for ep in existing_portfolios:
                # Remove all associated positions
                for pos in ep.positions:
                    db.delete(pos)
                db.delete(ep)
            db.flush()

            # Create new Portfolio
            db_portfolio = Portfolio(
                name=final_portfolio.broker_name,
                broker=final_portfolio.broker_name,
                description=f"Uploaded at {final_portfolio.imported_at.isoformat()}",
                user_id=current_user.id,
            )
            db.add(db_portfolio)
            db.flush()
            db.refresh(db_portfolio)

            # Create Positions
            for stock_pos in final_portfolio.positions:
                db_pos = Position(
                    asset_name=stock_pos.name or f"Asset {stock_pos.ticker}",
                    ticker=stock_pos.ticker,
                    isin=None,  # Will be resolved or left None
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
        except Exception:
            db.rollback()
            logger.exception("Unexpected error during portfolio upload")
            raise HTTPException(
                status_code=500, detail="An unexpected error occurred."
            ) from None
        db.refresh(db_portfolio)

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
            },
        )

    except HTTPException as e:
        # Re-raise HTTP exceptions (like our 500 DB errors) to be handled by FastAPI
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
            },
        )
