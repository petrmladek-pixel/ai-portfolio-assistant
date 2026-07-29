"""Tests for web routes and dashboard functionality."""

import warnings
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from portfolio_assistant.main import app
from portfolio_assistant.models.portfolio import (
    Currency,
    ImportedPortfolio,
    StockPosition,
)
from portfolio_assistant.models.valuation import ValuedPortfolio, ValuedPosition

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
    # Create mock portfolio data
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

    # Create mock valued portfolio
    mock_valued_positions = [
        ValuedPosition(
            ticker="AAPL",
            name="Apple Inc.",
            quantity=Decimal("10"),
            unit_price_original=Decimal("180.75"),
            currency_original=Currency.USD,
            unit_price_target=Decimal("4000.00"),  # Mock CZK value
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
            unit_price_target=Decimal("8000.00"),  # Mock CZK value
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

    # Mock CSV content (simplified DEGIRO format)
    csv_content = """Product,Symbol/ISIN,Quantity,Break-even Price,Currency
Apple Inc.,AAPL,10,150.50,USD
Microsoft Corp.,MSFT,5,300.25,USD"""

    # Create mock file
    files = {"file": ("portfolio.csv", csv_content, "text/csv")}

    # Patch the service getter functions
    with (
        patch("portfolio_assistant.routers.web.get_portfolio_parser") as mock_parser,
        patch("portfolio_assistant.routers.web.get_valuation_service") as mock_val,
    ):
        # Setup mock parser
        mock_parser_instance = MagicMock()
        mock_parser_instance.parse_sync.return_value = mock_imported_portfolio
        mock_parser.return_value = mock_parser_instance

        # Setup mock valuation service
        mock_val_instance = MagicMock()
        mock_val_instance.value_portfolio_async.return_value = mock_valued_portfolio
        mock_val_instance.value_portfolio_async = AsyncMock(
            return_value=mock_valued_portfolio
        )
        mock_val.return_value = mock_val_instance

        # Make the request
        response = client.post("/upload", files=files)

        # Assertions
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

        # Check that the template contains expected data
        content = response.text
        assert "Portfolio Summary" in content
        assert "AAPL" in content
        assert "MSFT" in content
        assert "60 000,00" in content  # Formatted total value
        assert "CZK" in content

        # Check that chart data is present
        assert "allocationChart" in content
        assert "AAPL" in content
        assert "MSFT" in content


def test_post_upload_invalid_csv():
    """Test that POST /upload with invalid CSV shows error message."""
    # Create invalid CSV content
    csv_content = """Invalid,Header,Format
This,is,not,a,valid,CSV"""

    files = {"file": ("invalid.csv", csv_content, "text/csv")}

    # Patch the parser to raise an exception
    with patch("portfolio_assistant.routers.web.get_portfolio_parser") as mock_parser:
        mock_parser_instance = MagicMock()
        mock_parser_instance.parse_sync.side_effect = ValueError("Invalid CSV format")
        mock_parser.return_value = mock_parser_instance

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
