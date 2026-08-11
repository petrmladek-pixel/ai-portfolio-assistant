"""Web routes for the portfolio dashboard."""

import json
import logging
from decimal import Decimal
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from portfolio_assistant.models.portfolio import Currency
from portfolio_assistant.services.ai.gemini import GeminiAIService
from portfolio_assistant.services.market_data.yfinance import YFinanceMarketDataService
from portfolio_assistant.services.parser.degiro import DegiroPortfolioParser
from portfolio_assistant.services.parser.fio_broker import FioBrokerPortfolioParser
from portfolio_assistant.services.portfolio_merger import PortfolioMerger
from portfolio_assistant.services.valuation.engine import ValuationService

from ..dependencies import verify_credentials

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
    request: Request, username: Annotated[str, Depends(verify_credentials)]
) -> HTMLResponse:
    """Render the dashboard with upload form."""
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "valued_portfolio": None,
            "total_value_formatted": None,
            "chart_data_json": None,
            "error": None,
            "username": username,
            "ai_analysis_markdown": "",
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
    username: Annotated[str, Depends(verify_credentials)],
    degiro_file: Annotated[UploadFile | None, Form()] = None,
    fio_file: Annotated[UploadFile | None, Form()] = None,
) -> HTMLResponse:
    """Handle portfolio CSV upload and display valuation results."""
    try:
        imported_portfolios = []

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

        if not imported_portfolios:
            raise ValueError("No portfolio files provided for upload")

        # Merge portfolios if multiple files were provided
        if len(imported_portfolios) > 1:
            merged_portfolio = portfolio_merger.merge_portfolios(imported_portfolios)
            imported_portfolios = [merged_portfolio]

        # Use the final portfolio (either single or merged)
        final_portfolio = imported_portfolios[0]

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
                "username": username,
                "ai_analysis_markdown": ai_analysis_markdown,
            },
        )

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
                "username": username,
            },
        )
