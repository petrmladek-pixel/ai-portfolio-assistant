"""Unit tests for the market data services."""

from decimal import Decimal
from unittest.mock import patch

import pandas as pd
import pytest

from portfolio_assistant.services.market_data.yfinance import YFinanceMarketDataService


@pytest.mark.asyncio
async def test_yfinance_get_current_prices_empty():
    """Test get_current_prices with an empty list of tickers."""
    service = YFinanceMarketDataService()
    prices = await service.get_current_prices([])
    assert prices == {}


@pytest.mark.asyncio
async def test_yfinance_get_current_prices_single():
    """Test get_current_prices with a single ticker and mocked response."""
    service = YFinanceMarketDataService()

    # Mock yf.download to return a DataFrame for a single ticker
    mock_df = pd.DataFrame({"Close": [150.50]}, index=[pd.Timestamp("2026-07-29")])

    with patch("yfinance.download", return_value=mock_df) as mock_download:
        prices = await service.get_current_prices(["AAPL"])

        mock_download.assert_called_once_with(["AAPL"], period="1d", progress=False)
        assert prices == {"AAPL": Decimal("150.5")}


@pytest.mark.asyncio
async def test_yfinance_get_current_prices_multiple():
    """Test get_current_prices with multiple tickers and mocked response."""
    service = YFinanceMarketDataService()

    # Mock yf.download to return a DataFrame with MultiIndex columns
    columns = pd.MultiIndex.from_tuples([("Close", "AAPL"), ("Close", "MSFT")])
    mock_df = pd.DataFrame(
        [[150.50, 350.25]],
        columns=columns,
        index=[pd.Timestamp("2026-07-29")],
    )

    with patch("yfinance.download", return_value=mock_df) as mock_download:
        prices = await service.get_current_prices(["AAPL", "MSFT"])

        mock_download.assert_called_once_with(
            ["AAPL", "MSFT"],
            period="1d",
            progress=False,
        )
        assert prices == {
            "AAPL": Decimal("150.5"),
            "MSFT": Decimal("350.25"),
        }


@pytest.mark.asyncio
async def test_yfinance_get_exchange_rate_same_currency():
    """Test get_exchange_rate with the same currency (shortcut)."""
    service = YFinanceMarketDataService()

    with patch("yfinance.download") as mock_download:
        rate = await service.get_exchange_rate("USD", "USD")
        assert rate == Decimal("1.0")
        mock_download.assert_not_called()


@pytest.mark.asyncio
async def test_yfinance_get_exchange_rate_different_currency():
    """Test get_exchange_rate with different currencies and mocked response."""
    service = YFinanceMarketDataService()

    # Mock yf.download for exchange rate ticker, returning a Close column
    mock_df = pd.DataFrame({"Close": [23.456]}, index=[pd.Timestamp("2026-07-29")])

    with patch("yfinance.download", return_value=mock_df) as mock_download:
        rate = await service.get_exchange_rate("USD", "CZK")

        mock_download.assert_called_once_with("USDCZK=X", period="1d", progress=False)
        assert rate == Decimal("23.456")


@pytest.mark.asyncio
async def test_yfinance_get_exchange_rate_failure():
    """Test get_exchange_rate failure cases."""
    service = YFinanceMarketDataService()

    # Return empty DataFrame
    mock_df = pd.DataFrame()

    with patch("yfinance.download", return_value=mock_df):
        with pytest.raises(ValueError, match="Could not fetch exchange rate"):
            await service.get_exchange_rate("USD", "CZK")
