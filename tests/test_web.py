"""Tests for web routes and dashboard functionality."""

import warnings
from datetime import datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from portfolio_assistant.core.database import get_db_session
from portfolio_assistant.dependencies import (
    get_current_user,
    get_optional_current_user,
)
from portfolio_assistant.main import app
from portfolio_assistant.models.db_models import Portfolio
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
    """Test that GET / returns 200 OK and contains expected content."""
    # Test without authentication (public access)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Ukázka (Read-only)" in response.text
    assert "10 000 000,00" in response.text

    # Test with authenticated user
    mock_user = User(id=1, email="admin@example.com", hashed_password="hash")
    app.dependency_overrides[get_optional_current_user] = lambda: mock_user
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "admin@example.com" in response.text
        assert "Nahrát CSV data" in response.text
    finally:
        _teardown_mock_services()


def test_dashboard_guest_mode():
    """Test that GET / as guest returns Berkshire Hathaway demo data."""
    response = client.get("/")
    assert response.status_code == 200
    content = response.text
    assert "Ukázka (Read-only)" in content
    assert "10 000 000,00" in content
    assert "AAPL" in content
    assert "OXY" in content
    assert "Analyzujte vlastní data" in content


@pytest.fixture(name="test_db_session")
def get_test_db_session(db_session: Session):
    """Override get_db_session to use test database session."""
    yield db_session


def test_post_upload_only_degiro_csv(test_db_session: Session):
    """Test that POST /upload with only DEGIRO CSV processes successfully."""
    app.dependency_overrides[get_db_session] = lambda: test_db_session

    user = User(email="upload@example.com", hashed_password="hash")
    test_db_session.add(user)
    test_db_session.commit()
    test_db_session.refresh(user)

    portfolio = Portfolio(name="Test", broker="DEGIRO", user_id=user.id)
    test_db_session.add(portfolio)
    test_db_session.commit()
    test_db_session.refresh(portfolio)

    mock_imported_portfolio, mock_valued_portfolio = _create_mock_portfolio_data()
    mock_degiro_parser, _, mock_portfolio_merger, mock_valuation_service, _ = (
        _setup_mock_services(mock_imported_portfolio, mock_valued_portfolio)
    )

    degiro_csv_content = """Product,Symbol/ISIN,Quantity,Break-even Price,Currency\n"
        "Apple Inc.,AAPL,10,150.50,USD\nMicrosoft Corp.,MSFT,5,300.25,USD"""

    files: dict[str, Any] = {"file": ("degiro.csv", degiro_csv_content, "text/csv")}
    data = {"portfolio_id": str(portfolio.id), "import_type": "degiro"}

    app.dependency_overrides[get_current_user] = lambda: user

    try:
        response = client.post(
            "/upload",
            files=files,
            data=data,
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        content = response.text
        assert "AAPL" in content
        mock_degiro_parser.parse.assert_called_once()
        mock_valuation_service.value_portfolio_async.assert_called_once()

    finally:
        _teardown_mock_services()


def test_post_upload_only_fio_csv(test_db_session: Session):
    """Test that POST /upload with only Fio CSV processes successfully."""
    app.dependency_overrides[get_db_session] = lambda: test_db_session

    user = User(email="fio@example.com", hashed_password="hash")
    test_db_session.add(user)
    test_db_session.commit()
    test_db_session.refresh(user)

    portfolio = Portfolio(name="Fio", broker="Fio", user_id=user.id)
    test_db_session.add(portfolio)
    test_db_session.commit()
    test_db_session.refresh(portfolio)

    mock_imported_portfolio, mock_valued_portfolio = _create_mock_portfolio_data()
    _, mock_fio_parser, mock_portfolio_merger, mock_valuation_service, _ = (
        _setup_mock_services(mock_imported_portfolio, mock_valued_portfolio)
    )

    fio_csv_content = """Pohyb,Datum,N\xc3\xa1zev cenn\xc3\xa9ho pap\xc3\xadru,ISIN,Mno"
        "N\xc5\xbestv\xc3\xad,Kurz,M\xc4\x9bna\n"
        "N\xc3\xa1kup,2023-01-01,Apple Inc.,US0378331005,10,150.50,USD\n"
        "N\xc3\xa1kup,2023-01-02,Microsoft Corp.,US5949181045,5,300.25,USD"""

    files: dict[str, Any] = {"file": ("fio.csv", fio_csv_content, "text/csv")}
    data = {"portfolio_id": str(portfolio.id), "import_type": "fio"}

    app.dependency_overrides[get_current_user] = lambda: user

    try:
        response = client.post(
            "/upload",
            files=files,
            data=data,
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "AAPL" in response.text
        mock_fio_parser.parse.assert_called_once()
    finally:
        _teardown_mock_services()


def test_post_upload_no_files_raises_400(test_db_session: Session):
    """Test that POST /upload with no files raises HTTP 400 error."""
    app.dependency_overrides[get_db_session] = lambda: test_db_session

    user = User(email="nofiles@example.com", hashed_password="hash")
    test_db_session.add(user)
    test_db_session.commit()
    test_db_session.refresh(user)

    portfolio = Portfolio(name="T", broker="B", user_id=user.id)
    test_db_session.add(portfolio)
    test_db_session.commit()

    files: dict[str, Any] = {}
    data = {"portfolio_id": str(portfolio.id), "import_type": "degiro"}

    app.dependency_overrides[get_current_user] = lambda: user

    try:
        response = client.post("/upload", files=files, data=data)
        assert response.status_code == 422
    finally:
        _teardown_mock_services()


def test_post_upload_invalid_csv(test_db_session: Session):
    """Test that POST /upload with invalid CSV shows error message."""
    app.dependency_overrides[get_db_session] = lambda: test_db_session
    user = User(email="invalid@example.com", hashed_password="hash")
    test_db_session.add(user)
    test_db_session.commit()
    portfolio = Portfolio(name="T", broker="B", user_id=user.id)
    test_db_session.add(portfolio)
    test_db_session.commit()

    csv_content = """Invalid,Header,Format\nThis,is,not,a,valid,CSV"""
    files: dict[str, Any] = {"file": ("invalid.csv", csv_content, "text/csv")}
    data = {"portfolio_id": str(portfolio.id), "import_type": "degiro"}

    app.dependency_overrides[get_current_user] = lambda: user
    mock_parser_service = MagicMock()
    mock_parser_service.parse = AsyncMock(side_effect=ValueError("Invalid CSV format"))
    app.dependency_overrides[get_portfolio_parser] = lambda: mock_parser_service

    try:
        response = client.post("/upload", files=files, data=data)
        assert response.status_code == 200
        assert "Error processing portfolio" in response.text
    finally:
        _teardown_mock_services()
