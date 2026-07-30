"""Web routes for the portfolio dashboard."""

import json
from decimal import Decimal
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from portfolio_assistant.models.portfolio import Currency
from portfolio_assistant.services.market_data.yfinance import YFinanceMarketDataService
from portfolio_assistant.services.parser.degiro import DegiroPortfolioParser
from portfolio_assistant.services.valuation.engine import ValuationService


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


def get_portfolio_parser() -> DegiroPortfolioParser:
    """FastAPI dependency: Get portfolio parser instance."""
    return DegiroPortfolioParser()


@router.get("/", response_class=HTMLResponse)
async def dashboard_get(request: Request) -> HTMLResponse:
    """Render the dashboard with upload form."""
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "valued_portfolio": None,
            "total_value_formatted": None,
            "chart_data_json": None,
            "error": None,
        },
    )


@router.post("/upload", response_class=HTMLResponse)
async def upload_portfolio(
    request: Request,
    file: Annotated[UploadFile, Form()],
    valuation_service: Annotated[ValuationService, Depends(get_valuation_service)],
    portfolio_parser: Annotated[DegiroPortfolioParser, Depends(get_portfolio_parser)],
) -> HTMLResponse:
    """Handle portfolio CSV upload and display valuation results."""
    try:
        # Read and parse the uploaded file
        file_content = await file.read()
        imported_portfolio = portfolio_parser.parse_sync(file_content)

        # Value the portfolio
        valued_portfolio = await valuation_service.value_portfolio_async(
            imported_portfolio, target_currency=Currency.CZK
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
            },
        )

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "valued_portfolio": None,
                "total_value_formatted": None,
                "chart_data_json": None,
                "error": f"Error processing portfolio: {str(e)}",
            },
        )
