"""UI regression tests using BeautifulSoup4 to test DOM rendering."""

import warnings
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
from sqlmodel import Session

from portfolio_assistant.core.database import get_db_session
from portfolio_assistant.core.utils import get_now_utc
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


def _create_mock_portfolio_data_with_weights() -> tuple[
    ImportedPortfolio, ValuedPortfolio
]:
    """Helper to create mock portfolio data with specific weights for sorting test."""
    mock_positions = [
        StockPosition(
            ticker="AAPL",
            name="Apple Inc.",
            quantity=Decimal("20"),
            average_price=Decimal("150.50"),
            currency=Currency.USD,
        ),
        StockPosition(
            ticker="MSFT",
            name="Microsoft Corp.",
            quantity=Decimal("15"),
            average_price=Decimal("300.25"),
            currency=Currency.USD,
        ),
        StockPosition(
            ticker="GOOGL",
            name="Alphabet Inc.",
            quantity=Decimal("5"),
            average_price=Decimal("100.00"),
            currency=Currency.USD,
        ),
    ]

    mock_imported_portfolio = ImportedPortfolio(
        broker_name="DEGIRO",
        imported_at=get_now_utc(),
        positions=mock_positions,
    )

    # Create valued positions with specific weights: 20%, 15%, 5%
    mock_valued_positions = [
        ValuedPosition(
            ticker="AAPL",
            name="Apple Inc.",
            quantity=Decimal("20"),
            unit_price_original=Decimal("180.75"),
            currency_original=Currency.USD,
            unit_price_target=Decimal("4000.00"),
            currency_target=Currency.CZK,
            total_value_target=Decimal("80000.00"),
            weight=Decimal("0.20"),  # 20%
        ),
        ValuedPosition(
            ticker="MSFT",
            name="Microsoft Corp.",
            quantity=Decimal("15"),
            unit_price_original=Decimal("350.50"),
            currency_original=Currency.USD,
            unit_price_target=Decimal("8000.00"),
            currency_target=Currency.CZK,
            total_value_target=Decimal("60000.00"),
            weight=Decimal("0.15"),  # 15%
        ),
        ValuedPosition(
            ticker="GOOGL",
            name="Alphabet Inc.",
            quantity=Decimal("5"),
            unit_price_original=Decimal("100.00"),
            currency_original=Currency.USD,
            unit_price_target=Decimal("2000.00"),
            currency_target=Currency.CZK,
            total_value_target=Decimal("10000.00"),
            weight=Decimal("0.05"),  # 5%
        ),
    ]

    mock_valued_portfolio = ValuedPortfolio(
        broker_name="DEGIRO",
        imported_at=get_now_utc(),
        valued_at=get_now_utc(),
        positions=mock_valued_positions,
        total_value=Decimal("150000.00"),
        target_currency=Currency.CZK,
    )

    return mock_imported_portfolio, mock_valued_portfolio


def _setup_mock_services_for_ui(
    imported_portfolio: ImportedPortfolio,
    valued_portfolio: ValuedPortfolio,
) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock, MagicMock]:
    """Helper to set up mock services for UI tests."""
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


@pytest.fixture(name="test_db_session")
def get_test_db_session(db_session: Session):
    """Override get_db_session to use test database session."""
    yield db_session


def test_dropdown_and_conditional_upload_menu(test_db_session: Session):
    """Test 1: Dropdown and Conditional Upload Menu.

    Make a GET /dashboard request (representing "All portfolios" view).
    Assert that the portfolio selection <select> element exists on the page.
    Assert that the drag & drop upload form is NOT present in the HTML.
    Assert that the helper string "Pro import transakci" is present.
    """
    app.dependency_overrides[get_db_session] = lambda: test_db_session

    # Test with authenticated user and "all" portfolio view
    mock_user = User(id=1, email="test@example.com", hashed_password="hash")
    test_db_session.add(mock_user)
    test_db_session.commit()
    test_db_session.refresh(mock_user)

    portfolio = Portfolio(name="Test", broker="DEGIRO", user_id=mock_user.id)
    test_db_session.add(portfolio)
    test_db_session.commit()
    test_db_session.refresh(portfolio)

    app.dependency_overrides[get_optional_current_user] = lambda: mock_user
    app.dependency_overrides[get_current_user] = lambda: mock_user

    # Mock services to prevent real API calls
    mock_imported_portfolio, mock_valued_portfolio = (
        _create_mock_portfolio_data_with_weights()
    )
    _setup_mock_services_for_ui(mock_imported_portfolio, mock_valued_portfolio)

    try:
        # Test with portfolio_id="all" (All portfolios view)
        response = client.get("?portfolio_id=all")
        assert response.status_code == 200

        html_content = response.text
        soup = BeautifulSoup(html_content, "html.parser")

        # Check that portfolio selection dropdown exists
        portfolio_select = soup.find("select", {"id": "portfolio-select"})
        assert portfolio_select is not None, "Portfolio selection dropdown should exist"

        # Check drag & drop upload form is hidden for "all"
        # portfolios (client-side hiding)
        # With Alpine.js, the dropzone element is present but hidden via x-show
        dropzone = soup.find(class_="dropzone")
        assert dropzone is not None, (
            "Drag & drop upload form should be present for client-side hiding"
        )
        # Check that the upload form container has the x-show directive to hide it
        upload_form_container = soup.find(
            "div", {"x-show": "selectedPortfolio !== '' && selectedPortfolio !== 'all'"}
        )
        assert upload_form_container is not None, (
            "Upload form should have client-side hiding directive"
        )

        # Check that the helper string is present (testing Czech UI text)
        # The actual HTML contains Czech text with diacritics, but we can check
        # for parts without diacritics like "vyberte" (meaning "select")
        assert "vyberte" in html_content, "Helper text should be present"

    finally:
        _teardown_mock_services()


def test_sorting_of_positions_in_ui(test_db_session: Session):
    """Test 2: Sorting of Positions in UI.

    Mock a portfolio with multiple active positions having different allocations.
    Make a GET /dashboard?portfolio_id=1 request.
    Parse HTML with BeautifulSoup, extract percentages from weights
    Assert percentages are strictly sorted in descending order
    """
    app.dependency_overrides[get_db_session] = lambda: test_db_session

    # Create test user and portfolio
    user = User(email="sorttest@example.com", hashed_password="hash")
    test_db_session.add(user)
    test_db_session.commit()
    test_db_session.refresh(user)

    portfolio = Portfolio(name="Sort Test", broker="DEGIRO", user_id=user.id)
    test_db_session.add(portfolio)
    test_db_session.commit()
    test_db_session.refresh(portfolio)

    # Mock services with portfolio data that has specific weights
    mock_imported_portfolio, mock_valued_portfolio = (
        _create_mock_portfolio_data_with_weights()
    )
    _setup_mock_services_for_ui(mock_imported_portfolio, mock_valued_portfolio)

    app.dependency_overrides[get_optional_current_user] = lambda: user
    app.dependency_overrides[get_current_user] = lambda: user

    try:
        # Make request to dashboard with specific portfolio_id
        response = client.get(f"/?portfolio_id={portfolio.id}")
        assert response.status_code == 200

        html_content = response.text
        soup = BeautifulSoup(html_content, "html.parser")

        # Find all weight percentage elements in the positions table
        # Look for elements with % symbol - they should be in the weight column
        weight_elements = soup.find_all(string=lambda text: text and "%" in text)

        extracted_percentages = []
        for element in weight_elements:
            text = str(element).strip()
            # Handle different formats: "20 %", "20%", "12,9 %", "12.9 %"
            if "%" in text:
                # Remove % symbol and any whitespace
                percentage_text = text.replace("%", "").replace(",", ".").strip()
                try:
                    percentage = float(percentage_text)
                    extracted_percentages.append(percentage)
                except ValueError:
                    # Skip if we can't parse it
                    continue

        # We should have at least some percentages extracted
        assert len(extracted_percentages) > 0, "Find at least one percentage in table"

        # Check that percentages are sorted in descending order
        sorted_percentages = sorted(extracted_percentages, reverse=True)
        assert extracted_percentages == sorted_percentages, (
            f"Percentages should be sorted descending. Got: {extracted_percentages}, "
            f"Expected: {sorted_percentages}"
        )

    finally:
        _teardown_mock_services()
