"""Tests for web routes and dashboard functionality."""

import warnings
from datetime import datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from portfolio_assistant.dependencies import get_optional_current_user
from portfolio_assistant.main import app
from portfolio_assistant.models.portfolio import (
    Currency,
    ImportedPortfolio,
    StockPosition,
)
from portfolio_assistant.models.user import User
from portfolio_assistant.models.valuation import ValuedPortfolio, ValuedPosition
from portfolio_assistant.routers.web import (
    get_fio_parser,
    get_gemini_service,
    get_portfolio_merger,
    get_portfolio_parser,
    get_valuation_service,
)

# Suppress the httpx deprecation warning
warnings.filterwarnings("ignore", message=".*httpx.*", category=DeprecationWarning)
client = TestClient(app)


def _create_mock_portfolio_data() -> tuple[ImportedPortfolio, ValuedPortfolio]:
    """Helper to create common mock portfolio data."""
    mock_positions = [
        StockPosition(
            ticker="AAPL",
            name="Apple Inc.",
            quantity=Decimal("10"),
            average_price=Decimal("150.50"),
            currency=Currency.USD,
        ),
        StockPosition(
            ticker="MSFT",
            name="Microsoft Corp.",
            quantity=Decimal("5"),
            average_price=Decimal("300.25"),
            currency=Currency.USD,
        ),
    ]

    mock_imported_portfolio = ImportedPortfolio(
        broker_name="DEGIRO",
        imported_at=datetime.now(),
        positions=mock_positions,
    )

    mock_valued_positions = [
        ValuedPosition(
            ticker="AAPL",
            name="Apple Inc.",
            quantity=Decimal("10"),
            unit_price_original=Decimal("180.75"),
            currency_original=Currency.USD,
            unit_price_target=Decimal("4000.00"),
            currency_target=Currency.CZK,
            total_value_target=Decimal("40000.00"),
            weight=Decimal("0.6667"),
        ),
        ValuedPosition(
            ticker="MSFT",
            name="Microsoft Corp.",
            quantity=Decimal("5"),
            unit_price_original=Decimal("350.50"),
            currency_original=Currency.USD,
            unit_price_target=Decimal("8000.00"),
            currency_target=Currency.CZK,
            total_value_target=Decimal("20000.00"),
            weight=Decimal("0.3333"),
        ),
    ]

    mock_valued_portfolio = ValuedPortfolio(
        broker_name="DEGIRO",
        imported_at=datetime.now(),
        valued_at=datetime.now(),
        positions=mock_valued_positions,
        total_value=Decimal("60000.00"),
        target_currency=Currency.CZK,
    )

    return mock_imported_portfolio, mock_valued_portfolio


def _setup_mock_services(
    imported_portfolio: ImportedPortfolio,
    valued_portfolio: ValuedPortfolio,
) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock, MagicMock]:
    """Helper to set up mock services for tests."""
    mock_degiro_parser = MagicMock()
    mock_degiro_parser.parse = AsyncMock(return_value=imported_portfolio)

    mock_fio_parser = MagicMock()
    mock_fio_parser.parse = AsyncMock(return_value=imported_portfolio)

    mock_portfolio_merger = MagicMock()
    mock_portfolio_merger.merge_portfolios = MagicMock(return_value=imported_portfolio)

    mock_valuation_service = MagicMock()
    mock_valuation_service.value_portfolio_async = AsyncMock(
        return_value=valued_portfolio
    )

    mock_gemini_service = MagicMock()
    mock_gemini_service.analyze_portfolio = AsyncMock(return_value="AI Analysis")

    app.dependency_overrides[get_portfolio_parser] = lambda: mock_degiro_parser
    app.dependency_overrides[get_fio_parser] = lambda: mock_fio_parser
    app.dependency_overrides[get_portfolio_merger] = lambda: mock_portfolio_merger
    app.dependency_overrides[get_valuation_service] = lambda: mock_valuation_service
    app.dependency_overrides[get_gemini_service] = lambda: mock_gemini_service

    return (
        mock_degiro_parser,
        mock_fio_parser,
        mock_portfolio_merger,
        mock_valuation_service,
        mock_gemini_service,
    )


def _teardown_mock_services() -> None:
    """Helper to clean up dependency overrides."""
    app.dependency_overrides.clear()


def test_get_dashboard():
    """Test that GET / returns 200 OK and contains upload form."""
    # Test without authentication (public access)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert b"Register" in response.content  # Assuming registration link is visible
    assert b"Login" in response.content  # Assuming login link is visible
    assert b"Get Started" in response.content  # New prompt for unauthenticated users
    assert (
        b"Upload Portfolio CSV" not in response.content
    )  # Upload form should be hidden

    # Test with authenticated user
    mock_user = User(email="admin@example.com", hashed_password="hash")
    app.dependency_overrides[get_optional_current_user] = lambda: mock_user
    try:
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert (
            b"admin@example.com" in response.content
        )  # Check if username is displayed
        assert (
            b"Upload Portfolio CSV" in response.content
        )  # Upload form should be visible
        assert b"Get Started" not in response.content  # Prompt should be hidden
    finally:
        _teardown_mock_services()


def test_post_upload_only_degiro_csv():
    """Test that POST /upload with only DEGIRO CSV processes successfully."""
    mock_imported_portfolio, mock_valued_portfolio = _create_mock_portfolio_data()
    mock_degiro_parser, _, mock_portfolio_merger, mock_valuation_service, _ = (
        _setup_mock_services(mock_imported_portfolio, mock_valued_portfolio)
    )

    degiro_csv_content = """Product,Symbol/ISIN,Quantity,Break-even Price,Currency\n"
        "Apple Inc.,AAPL,10,150.50,USD\nMicrosoft Corp.,MSFT,5,300.25,USD"""

    files: dict[str, Any] = {
        "degiro_file": ("degiro.csv", degiro_csv_content, "text/csv")
    }

    # Mock authenticated user
    mock_user = User(email="admin@example.com", hashed_password="hash")
    app.dependency_overrides[get_optional_current_user] = lambda: mock_user

    try:
        response = client.post("/upload", files=files)

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        content = response.text
        assert "Portfolio Summary" in content
        assert "AAPL" in content
        assert "MSFT" in content
        assert "60 000,00" in content
        assert "CZK" in content
        mock_degiro_parser.parse.assert_called_once()
        mock_portfolio_merger.merge_portfolios.assert_not_called()
        mock_valuation_service.value_portfolio_async.assert_called_once()

    finally:
        _teardown_mock_services()


def test_post_upload_only_fio_csv():
    """Test that POST /upload with only Fio CSV processes successfully."""
    mock_imported_portfolio, mock_valued_portfolio = _create_mock_portfolio_data()
    _, mock_fio_parser, mock_portfolio_merger, mock_valuation_service, _ = (
        _setup_mock_services(mock_imported_portfolio, mock_valued_portfolio)
    )

    fio_csv_content = """Pohyb,Datum,Název cenného papíru,ISIN,Množství,Kurz,Měna\n"
        "Nákup,2023-01-01,Apple Inc.,US0378331005,10,150.50,USD\n"
        "Nákup,2023-01-02,Microsoft Corp.,US5949181045,5,300.25,USD"""

    files: dict[str, Any] = {"fio_file": ("fio.csv", fio_csv_content, "text/csv")}

    # Mock authenticated user
    mock_user = User(email="admin@example.com", hashed_password="hash")
    app.dependency_overrides[get_optional_current_user] = lambda: mock_user

    try:
        response = client.post("/upload", files=files)

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        content = response.text
        assert "Portfolio Summary" in content
        assert "AAPL" in content
        assert "MSFT" in content
        assert "60 000,00" in content
        assert "CZK" in content
        mock_fio_parser.parse.assert_called_once()
        mock_portfolio_merger.merge_portfolios.assert_not_called()
        mock_valuation_service.value_portfolio_async.assert_called_once()

    finally:
        _teardown_mock_services()


def test_post_upload_no_files_raises_400():
    """Test that POST /upload with no files raises HTTP 400 error."""
    # No files provided
    files: dict[str, Any] = {}

    # Mock authenticated user
    mock_user = User(email="admin@example.com", hashed_password="hash")
    app.dependency_overrides[get_optional_current_user] = lambda: mock_user

    try:
        response = client.post("/upload", files=files)

        assert (
            response.status_code == 200
        )  # Expect 200 because it renders the dashboard with an error
        assert "text/html" in response.headers["content-type"]
        assert (
            "Error processing portfolio: 400: "
            "At least one portfolio file must be provided." in response.text
        )
    finally:
        _teardown_mock_services()


def test_post_upload_invalid_csv():
    """Test that POST /upload with invalid CSV shows error message."""
    # Create invalid CSV content
    csv_content = """Invalid,Header,Format\nThis,is,not,a,valid,CSV"""

    files: dict[str, Any] = {"degiro_file": ("invalid.csv", csv_content, "text/csv")}

    # Mock authenticated user
    mock_user = User(email="admin@example.com", hashed_password="hash")
    app.dependency_overrides[get_optional_current_user] = lambda: mock_user

    # Override dependencies in the FastAPI application
    mock_parser_service = MagicMock()
    mock_parser_service.parse = AsyncMock(side_effect=ValueError("Invalid CSV format"))
    app.dependency_overrides[get_portfolio_parser] = lambda: mock_parser_service

    try:
        response = client.post("/upload", files=files)

        # Assertions
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Error processing portfolio" in response.text
        assert "Invalid CSV format" in response.text
    finally:
        _teardown_mock_services()


def test_post_upload_empty_file():
    """Test that POST /upload with empty file shows error message."""
    files: dict[str, Any] = {"degiro_file": ("empty.csv", "", "text/csv")}

    # Mock authenticated user
    mock_user = User(email="admin@example.com", hashed_password="hash")
    app.dependency_overrides[get_optional_current_user] = lambda: mock_user

    try:
        response = client.post("/upload", files=files)

        # Should show error due to empty file
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Error processing portfolio" in response.text
    finally:
        _teardown_mock_services()
