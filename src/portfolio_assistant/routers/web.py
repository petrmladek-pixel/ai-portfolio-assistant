"""Web routes for the portfolio dashboard."""

from decimal import Decimal
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Form, Request, UploadFile
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

    # Convert to string and split into integer and decimal parts
    value_str = f"{value:.2f}"
    integer_part, decimal_part = value_str.split(".")

    # Add thousand separators
    formatted_integer = ""
    for i, char in enumerate(reversed(integer_part)):
        if i > 0 and i % 3 == 0:
            formatted_integer = " " + formatted_integer
        formatted_integer = char + formatted_integer

    return f"{formatted_integer},{decimal_part}"


# Set up templates
BASE_DIR = Path(__file__).parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Register custom Jinja2 filter
templates.env.filters["format_currency"] = format_currency

# Create router
router = APIRouter(prefix="", tags=["web"])


# Initialize services
def get_market_data_service() -> YFinanceMarketDataService:
    return YFinanceMarketDataService()


def get_valuation_service() -> ValuationService:
    return ValuationService(get_market_data_service())


def get_portfolio_parser() -> DegiroPortfolioParser:
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
            "chart_data": None,
            "error": None,
        },
    )


@router.post("/upload", response_class=HTMLResponse)
async def upload_portfolio(
    request: Request,
    file: Annotated[UploadFile, Form()],
) -> HTMLResponse:
    """Handle portfolio CSV upload and display valuation results."""
    try:
        # Read and parse the uploaded file
        file_content = await file.read()
        imported_portfolio = get_portfolio_parser().parse_sync(file_content)

        # Value the portfolio
        valued_portfolio = await get_valuation_service().value_portfolio_async(
            imported_portfolio, target_currency=Currency.CZK
        )

        # Prepare chart data
        chart_labels = [pos.ticker for pos in valued_portfolio.positions]
        chart_weights = [float(pos.weight * 100) for pos in valued_portfolio.positions]

        chart_data = {
            "labels": chart_labels,
            "weights": chart_weights,
        }

        # Format total value
        total_value_formatted = format_currency(valued_portfolio.total_value)

        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "valued_portfolio": valued_portfolio,
                "total_value_formatted": total_value_formatted,
                "chart_data": chart_data,
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
                "chart_data": None,
                "error": f"Error processing portfolio: {str(e)}",
            },
        )
