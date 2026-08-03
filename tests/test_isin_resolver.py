"""Tests for the Yahoo ISIN resolver with round-trip validation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx2 import AsyncClient, Response

from portfolio_assistant.services.isin_cache import SQLiteISINCache
from portfolio_assistant.services.isin_resolver import YahooISINResolver


@pytest.fixture
def mock_cache():
    """Fixture for creating a mock SQLite ISIN cache."""
    cache = MagicMock(spec=SQLiteISINCache)
    return cache


@pytest.fixture
def isin_resolver(mock_cache):
    """Fixture for creating a Yahoo ISIN resolver with mock cache."""
    return YahooISINResolver(cache=mock_cache)


@pytest.fixture
def mock_client_instance():
    """Fixture for creating a mock httpx2 AsyncClient instance."""
    client = AsyncMock(spec=AsyncClient)
    return client


@pytest.fixture
def mock_client_class(mock_client_instance):
    """Fixture for creating a mock httpx2 AsyncClient class."""
    client_class = MagicMock()
    client_class.return_value.__aenter__.return_value = mock_client_instance
    return client_class


def test_isin_resolver_initialization(isin_resolver, mock_cache):
    """Test that the ISIN resolver initializes correctly."""
    assert isin_resolver.cache == mock_cache
    assert "Mozilla" in isin_resolver.user_agent
    assert "Chrome" in isin_resolver.user_agent


@pytest.mark.asyncio
async def test_resolve_isin_empty(isin_resolver):
    """Test resolving an empty ISIN."""
    result = await isin_resolver.resolve_isin("")
    assert result is None


@pytest.mark.asyncio
async def test_resolve_isin_whitespace(isin_resolver):
    """Test resolving a whitespace-only ISIN."""
    result = await isin_resolver.resolve_isin("   ")
    assert result is None


@pytest.mark.asyncio
async def test_resolve_isin_cache_hit(isin_resolver, mock_cache):
    """Test resolving an ISIN that exists in cache."""
    test_isin = "US0378331005"
    cached_ticker = "AAPL"

    # Mock cache to return a cached value
    mock_cache.get_ticker.return_value = cached_ticker

    result = await isin_resolver.resolve_isin(test_isin)

    # Verify cache was checked
    mock_cache.get_ticker.assert_called_once_with(test_isin)

    # Verify no Yahoo API call was made
    assert result == cached_ticker


@pytest.mark.asyncio
async def test_resolve_isin_cache_miss_success(
    isin_resolver, mock_cache, mock_client_class, mock_client_instance
):
    """Test resolving an ISIN that's not in cache but Yahoo API returns valid data."""
    test_isin = "US0378331005"
    expected_ticker = "AAPL"

    # Mock cache to return None (cache miss)
    mock_cache.get_ticker.return_value = None

    # Mock Yahoo API response
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "quotes": [{"isin": test_isin, "symbol": expected_ticker}]
    }

    mock_client_instance.get.return_value = mock_response

    with patch(
        "portfolio_assistant.services.isin_resolver.AsyncClient", mock_client_class
    ):
        result = await isin_resolver.resolve_isin(test_isin)

    # Verify cache was checked first
    mock_cache.get_ticker.assert_called_once_with(test_isin)

    # Verify Yahoo API was called with correct URL
    expected_url = f"https://query2.finance.yahoo.com/v1/finance/search?q={test_isin}&quotesCount=5&newsCount=0"
    mock_client_instance.get.assert_called_once_with(
        expected_url, headers={"User-Agent": isin_resolver.user_agent}
    )

    # Verify cache was updated with the resolved ticker
    mock_cache.set_ticker.assert_called_once_with(test_isin, expected_ticker)

    # Verify correct ticker was returned
    assert result == expected_ticker


@pytest.mark.asyncio
async def test_resolve_isin_round_trip_validation_failure(
    isin_resolver, mock_cache, mock_client_class, mock_client_instance
):
    """Test resolving an ISIN where Yahoo API returns data but ISIN doesn't match."""
    test_isin = "US0378331005"

    # Mock cache to return None (cache miss)
    mock_cache.get_ticker.return_value = None

    # Mock Yahoo API response with different ISIN
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "quotes": [
            {
                "isin": "US0378331006",  # Different ISIN
                "symbol": "AAPL",
            }
        ]
    }

    mock_client_instance.get.return_value = mock_response

    with patch(
        "portfolio_assistant.services.isin_resolver.AsyncClient", mock_client_class
    ):
        result = await isin_resolver.resolve_isin(test_isin)

    # Verify cache was checked first
    mock_cache.get_ticker.assert_called_once_with(test_isin)

    # Verify Yahoo API was called
    mock_client_instance.get.assert_called_once()

    # Verify cache was NOT updated (no exact ISIN match)
    mock_cache.set_ticker.assert_not_called()

    # Verify None was returned (fail-closed behavior)
    assert result is None


@pytest.mark.asyncio
async def test_resolve_isin_api_failure(
    isin_resolver, mock_cache, mock_client_class, mock_client_instance
):
    """Test resolving an ISIN when Yahoo API fails."""
    test_isin = "US0378331005"

    # Mock cache to return None (cache miss)
    mock_cache.get_ticker.return_value = None

    # Mock Yahoo API failure
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 500

    mock_client_instance.get.return_value = mock_response

    with patch(
        "portfolio_assistant.services.isin_resolver.AsyncClient", mock_client_class
    ):
        result = await isin_resolver.resolve_isin(test_isin)

    # Verify cache was checked first
    mock_cache.get_ticker.assert_called_once_with(test_isin)

    # Verify Yahoo API was called
    mock_client_instance.get.assert_called_once()

    # Verify cache was NOT updated
    mock_cache.set_ticker.assert_not_called()

    # Verify None was returned (fail-closed behavior)
    assert result is None


@pytest.mark.asyncio
async def test_resolve_isin_no_quotes(
    isin_resolver, mock_cache, mock_client_class, mock_client_instance
):
    """Test resolving an ISIN when Yahoo API returns no quotes."""
    test_isin = "US0378331005"

    # Mock cache to return None (cache miss)
    mock_cache.get_ticker.return_value = None

    # Mock Yahoo API response with no quotes
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"quotes": []}

    mock_client_instance.get.return_value = mock_response

    with patch(
        "portfolio_assistant.services.isin_resolver.AsyncClient", mock_client_class
    ):
        result = await isin_resolver.resolve_isin(test_isin)

    # Verify cache was checked first
    mock_cache.get_ticker.assert_called_once_with(test_isin)

    # Verify Yahoo API was called
    mock_client_instance.get.assert_called_once()

    # Verify cache was NOT updated
    mock_cache.set_ticker.assert_not_called()

    # Verify None was returned
    assert result is None


@pytest.mark.asyncio
async def test_resolve_isin_exception_handling(
    isin_resolver, mock_cache, mock_client_class, mock_client_instance
):
    """Test resolving an ISIN when an exception occurs."""
    test_isin = "US0378331005"

    # Mock cache to return None (cache miss)
    mock_cache.get_ticker.return_value = None

    # Mock Yahoo API to raise an exception
    mock_client_instance.get.side_effect = Exception("API error")

    with patch(
        "portfolio_assistant.services.isin_resolver.AsyncClient", mock_client_class
    ):
        result = await isin_resolver.resolve_isin(test_isin)

    # Verify cache was checked first
    mock_cache.get_ticker.assert_called_once_with(test_isin)

    # Verify Yahoo API was called
    mock_client_instance.get.assert_called_once()

    # Verify cache was NOT updated
    mock_cache.set_ticker.assert_not_called()

    # Verify None was returned (fail-closed behavior)
    assert result is None


@pytest.mark.asyncio
async def test_resolve_isins_multiple(isin_resolver, mock_cache):
    """Test resolving multiple ISINs."""
    test_isins = ["US0378331005", "US5949181045", "INVALID"]

    # Mock cache responses
    mock_cache.get_ticker.side_effect = ["AAPL", None, None]

    # Mock the internal _query_yahoo_api method to avoid actual API calls
    with patch.object(
        isin_resolver, "_query_yahoo_api", new_callable=AsyncMock
    ) as mock_query:
        # Set up side effects for the mock
        async def query_side_effect(isin):
            if isin == "US5949181045":
                return "MSFT"
            else:
                return None

        mock_query.side_effect = query_side_effect

        results = await isin_resolver.resolve_isins(test_isins)

    # Verify results
    assert results == {"US0378331005": "AAPL", "US5949181045": "MSFT", "INVALID": None}

    # Verify cache was checked for all ISINs
    assert mock_cache.get_ticker.call_count == 3
