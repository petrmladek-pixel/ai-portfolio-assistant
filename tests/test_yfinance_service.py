"""Tests for the YFinanceService metadata caching service."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session

from portfolio_assistant.crud.ticker_metadata import (
    get_ticker_metadata,
    save_ticker_metadata,
)
from portfolio_assistant.models.ticker_metadata import TickerMetadata
from portfolio_assistant.services.yfinance_service import YFinanceService


@pytest.fixture
def yfinance_service(db_session: Session) -> YFinanceService:
    """Fixture for creating a YFinanceService instance with a test database session."""
    return YFinanceService(db_session)


@pytest.fixture
def mock_ticker_info():
    """Fixture for creating a mock yfinance Ticker.info dictionary."""
    return {
        "sector": "Technology",
        "country": "United States",
    }


def test_get_metadata_cache_hit(yfinance_service: YFinanceService) -> None:
    """Test that cached metadata is returned without calling yfinance."""
    # Pre-populate cache with valid data
    save_ticker_metadata(
        yfinance_service.db,
        "AAPL",
        sector="Technology",
        country="United States",
    )

    # Call the service
    with patch("portfolio_assistant.services.yfinance_service.yf") as mock_yf:
        result = yfinance_service.get_metadata("AAPL")

        # Verify yfinance was NOT called
        mock_yf.Ticker.assert_not_called()

        # Verify cached data was returned
        assert result.ticker == "AAPL"
        assert result.sector == "Technology"
        assert result.country == "United States"
        assert result.updated_at is not None


def test_get_metadata_cache_missing(
    yfinance_service: YFinanceService,
    mock_ticker_info: dict[str, str],
) -> None:
    """Test that yfinance is called when cache is missing."""
    # Mock yfinance to return valid data
    mock_ticker = MagicMock()
    mock_ticker.info = mock_ticker_info

    with patch(
        "portfolio_assistant.services.yfinance_service.yf.Ticker",
        return_value=mock_ticker,
    ) as mock_ticker_class:
        result = yfinance_service.get_metadata("AAPL")

        # Verify yfinance was called
        mock_ticker_class.assert_called_once_with("AAPL")

        # Verify data was saved to cache
        cached = get_ticker_metadata(yfinance_service.db, "AAPL")
        assert cached is not None
        assert cached.sector == "Technology"
        assert cached.country == "United States"

        # Verify result
        assert result.ticker == "AAPL"
        assert result.sector == "Technology"
        assert result.country == "United States"


def test_get_metadata_cache_expired(
    yfinance_service: YFinanceService,
    mock_ticker_info: dict[str, str],
) -> None:
    """Test that yfinance is called when cache is expired (31 days old)."""
    # Pre-populate cache with expired data (31 days old)
    expired_time = datetime.now(UTC) - timedelta(days=31)
    expired_metadata = TickerMetadata(
        ticker="AAPL",
        sector="Old Sector",
        country="Old Country",
        updated_at=expired_time,
    )
    yfinance_service.db.add(expired_metadata)
    yfinance_service.db.commit()

    # Mock yfinance to return new data
    mock_ticker = MagicMock()
    mock_ticker.info = mock_ticker_info

    with patch(
        "portfolio_assistant.services.yfinance_service.yf.Ticker",
        return_value=mock_ticker,
    ) as mock_ticker_class:
        result = yfinance_service.get_metadata("AAPL")

        # Verify yfinance was called
        mock_ticker_class.assert_called_once_with("AAPL")

        # Verify cache was updated with new data
        cached = get_ticker_metadata(yfinance_service.db, "AAPL")
        assert cached is not None
        assert cached.sector == "Technology"
        assert cached.country == "United States"

        # Verify result has new data
        assert result.ticker == "AAPL"
        assert result.sector == "Technology"
        assert result.country == "United States"


def test_get_metadata_cache_exactly_30_days(
    yfinance_service: YFinanceService,
    mock_ticker_info: dict[str, str],
) -> None:
    """Test that cache exactly 30 days old expires and fetches fresh data."""
    # Pre-populate cache with data exactly 30 days old
    exact_time = datetime.now(UTC) - timedelta(days=30)
    metadata = TickerMetadata(
        ticker="AAPL",
        sector="Old Sector",
        country="Old Country",
        updated_at=exact_time,
    )
    yfinance_service.db.add(metadata)
    yfinance_service.db.commit()

    # Mock yfinance to return new data
    mock_ticker = MagicMock()
    mock_ticker.info = mock_ticker_info

    # Call the service
    with patch(
        "portfolio_assistant.services.yfinance_service.yf.Ticker",
        return_value=mock_ticker,
    ) as mock_ticker_class:
        result = yfinance_service.get_metadata("AAPL")

        # Verify yfinance WAS called (30 days exactly means expired)
        mock_ticker_class.assert_called_once_with("AAPL")

        # Verify cache was updated with new data
        cached = get_ticker_metadata(yfinance_service.db, "AAPL")
        assert cached is not None
        assert cached.sector == "Technology"
        assert cached.country == "United States"

        # Verify result has new data
        assert result.ticker == "AAPL"
        assert result.sector == "Technology"
        assert result.country == "United States"


def test_get_metadata_api_failure(
    yfinance_service: YFinanceService,
) -> None:
    """Test that API failure results in Unknown values being cached."""
    # Mock yfinance to raise an exception
    with patch(
        "portfolio_assistant.services.yfinance_service.yf.Ticker",
        side_effect=Exception("Service unavailable"),
    ) as mock_ticker_class:
        result = yfinance_service.get_metadata("AAPL")

        # Verify yfinance was called
        mock_ticker_class.assert_called_once_with("AAPL")

        # Verify Unknown values were cached
        cached = get_ticker_metadata(yfinance_service.db, "AAPL")
        assert cached is not None
        assert cached.sector == "Unknown"
        assert cached.country == "Unknown"

        # Verify result has Unknown values
        assert result.ticker == "AAPL"
        assert result.sector == "Unknown"
        assert result.country == "Unknown"


def test_get_metadata_missing_fields(
    yfinance_service: YFinanceService,
) -> None:
    """Test that missing sector/country fields fall back to Unknown."""
    # Mock yfinance to return info without sector/country
    mock_ticker = MagicMock()
    mock_ticker.info = {}

    with patch(
        "portfolio_assistant.services.yfinance_service.yf.Ticker",
        return_value=mock_ticker,
    ) as mock_ticker_class:
        yfinance_service.get_metadata("AAPL")

        # Verify yfinance was called
        mock_ticker_class.assert_called_once_with("AAPL")

        # Verify Unknown values were cached
        cached = get_ticker_metadata(yfinance_service.db, "AAPL")
        assert cached is not None
        assert cached.sector == "Unknown"
        assert cached.country == "Unknown"


def test_get_metadata_none_values(
    yfinance_service: YFinanceService,
) -> None:
    """Test that None values for sector/country fall back to Unknown."""
    # Mock yfinance to return info with None values
    mock_ticker = MagicMock()
    mock_ticker.info = {"sector": None, "country": None}

    with patch(
        "portfolio_assistant.services.yfinance_service.yf.Ticker",
        return_value=mock_ticker,
    ) as mock_ticker_class:
        result = yfinance_service.get_metadata("AAPL")

        # Verify yfinance was called
        mock_ticker_class.assert_called_once_with("AAPL")

        # Verify Unknown values were cached
        assert result.sector == "Unknown"
        assert result.country == "Unknown"


def test_get_metadata_naive_datetime_from_sqlite(
    yfinance_service: YFinanceService,
) -> None:
    """Test that naive datetime from SQLite is handled correctly."""
    # Pre-populate cache with naive datetime (simulating SQLite behavior)
    naive_time = datetime.now() - timedelta(days=1)
    metadata = TickerMetadata(
        ticker="AAPL",
        sector="Technology",
        country="United States",
        updated_at=naive_time,
    )
    yfinance_service.db.add(metadata)
    yfinance_service.db.commit()

    # Force the cached object to have naive datetime
    yfinance_service.db.refresh(metadata)

    # Call the service
    with patch("portfolio_assistant.services.yfinance_service.yf") as mock_yf:
        result = yfinance_service.get_metadata("AAPL")

        # Verify yfinance was NOT called (1 day old is still valid)
        mock_yf.Ticker.assert_not_called()

        # Verify cached data was returned
        assert result.ticker == "AAPL"
        assert result.sector == "Technology"
        assert result.country == "United States"
