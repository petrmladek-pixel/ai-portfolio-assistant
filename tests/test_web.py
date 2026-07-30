"""Tests for web routes and dashboard functionality."""

import warnings
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from portfolio_assistant.main import app
from portfolio_assistant.models.portfolio import (
    Currency,
    ImportedPortfolio,
    StockPosition,
)
from portfolio_assistant.models.valuation import ValuedPortfolio, ValuedPosition
from portfolio_assistant.routers.web import (
    get_portfolio_parser,
    get_valuation_service,
)

# Suppress the httpx deprecation warning
warnings.filterwarnings("ignore", message=".*httpx.*", category=DeprecationWarning)
client = TestClient(app)


def test_get_dashboard():
    """Test that GET / returns 200 OK and contains upload form."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert b"Upload Portfolio CSV" in response.content
    assert b"Upload and Analyze" in response.content
    assert b"DEGIRO portfolio CSV file" in response.content


def test_post_upload_valid_csv():
    """Test that POST /upload with valid CSV processes successfully."""
    # 1. Create mock data (same as your original implementation)
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

    csv_content = """Product,Symbol/ISIN,Quantity,Break-even Price,Currency
Apple Inc.,AAPL,10,150.50,USD
Microsoft Corp.,MSFT,5,300.25,USD"""

    files = {"file": ("portfolio.csv", csv_content, "text/csv")}

    # Create mock instances
    mock_parser_instance = MagicMock()
    mock_parser_instance.parse_sync.return_value = mock_imported_portfolio

    mock_val_instance = MagicMock()
    mock_val_instance.value_portfolio_async = AsyncMock(
        return_value=mock_valued_portfolio
    )

    # Override dependencies in the FastAPI application
    app.dependency_overrides[get_portfolio_parser] = lambda: mock_parser_instance
    app.dependency_overrides[get_valuation_service] = lambda: mock_val_instance

    try:
        # Perform the request
        response = client.post("/upload", files=files)

        # Assertions
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

        content = response.text
        assert "Portfolio Summary" in content
        assert "AAPL" in content
        assert "MSFT" in content
        assert "60 000,00" in content  # Now it will ALWAYS be the mock value: 60 000,00
        assert "CZK" in content

        # Check that chart data is present (using safe JSON approach)
        assert "chart-data" in content
        assert "data-chart=" in content
        assert "allocationChart" in content
        assert "AAPL" in content
        assert "MSFT" in content

    finally:
        # 5. IMPORTANT: Clean up dependency overrides to keep other tests isolated
        app.dependency_overrides.clear()


def test_post_upload_invalid_csv():
    """Test that POST /upload with invalid CSV shows error message."""
    # Create invalid CSV content
    csv_content = """Invalid,Header,Format
This,is,not,a,valid,CSV"""

    files = {"file": ("invalid.csv", csv_content, "text/csv")}

    # Override dependencies in the FastAPI application
    mock_parser_service = MagicMock()
    mock_parser_service.parse_sync = MagicMock(
        side_effect=ValueError("Invalid CSV format")
    )
    app.dependency_overrides[get_portfolio_parser] = lambda: mock_parser_service

    response = client.post("/upload", files=files)

    # Assertions
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Error processing portfolio" in response.text
    assert "Invalid CSV format" in response.text


def test_post_upload_empty_file():
    """Test that POST /upload with empty file shows error message."""
    files = {"file": ("empty.csv", "", "text/csv")}

    response = client.post("/upload", files=files)

    # Should show error due to empty file
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Error processing portfolio" in response.text
