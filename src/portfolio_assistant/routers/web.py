"""Web routes for the portfolio dashboard."""

import json
import logging
import secrets
from decimal import Decimal
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates

from portfolio_assistant.config import get_settings
from portfolio_assistant.models.portfolio import Currency
from portfolio_assistant.services.market_data.yfinance import YFinanceMarketDataService
from portfolio_assistant.services.parser.degiro import DegiroPortfolioParser
from portfolio_assistant.services.valuation.engine import ValuationService

logger = logging.getLogger(__name__)

# Security setup for Basic Authentication
security = HTTPBasic()


def verify_credentials(
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
) -> str:
    """
    Verify basic authentication credentials against configuration settings.

    Uses secrets.compare_digest to prevent timing attacks.
    In production, credentials must be explicitly configured
    (enforced by Pydantic validator).
    In non-production environments, falls back to "admin"/"admin" for local testing.

    Args:
        credentials: HTTPBasicCredentials from FastAPI security dependency

    Returns:
        str: The authenticated username

    Raises:
        HTTPException: 401 Unauthorized if credentials are invalid
    """
    settings = get_settings()

    # Retrieve expected values from configuration
    expected_username = settings.web_basic_auth_username
    expected_password = settings.web_basic_auth_password

    # For non-production environments, allow fallback to "admin"/"admin" for
    # easy local testing
    # Production environments are already guarded by Pydantic validator to ensure
    # explicit configuration
    if settings.environment != "production":
        expected_username = expected_username or "admin"
        expected_password = expected_password or "admin"
    else:
        # In production, these should never be None due to Pydantic validation,
        # but we provide a safety net to ensure they're always strings
        expected_username = expected_username or ""
        expected_password = expected_password or ""

    # Use secrets.compare_digest to prevent timing attacks
    is_correct_username = secrets.compare_digest(
        credentials.username, str(expected_username)
    )
    is_correct_password = secrets.compare_digest(
        credentials.password, str(expected_password)
    )

    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


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
        },
    )


@router.post("/upload", response_class=HTMLResponse)
async def upload_portfolio(
    request: Request,
    file: Annotated[UploadFile, Form()],
    valuation_service: Annotated[ValuationService, Depends(get_valuation_service)],
    portfolio_parser: Annotated[DegiroPortfolioParser, Depends(get_portfolio_parser)],
    username: Annotated[str, Depends(verify_credentials)],
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
                "username": username,
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
