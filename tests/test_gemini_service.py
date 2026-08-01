"""Unit tests for GeminiAIService."""

import os
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from portfolio_assistant.config import get_settings
from portfolio_assistant.models.portfolio import (
    AnonymizedPortfolio,
    AnonymizedPosition,
    Currency,
)
from portfolio_assistant.services.ai.gemini import GeminiAIService


@pytest.fixture
def sample_portfolio() -> AnonymizedPortfolio:
    """Create a sample anonymized portfolio for testing."""
    return AnonymizedPortfolio(
        broker_name="Test Broker",
        imported_at=datetime(2023, 1, 1),
        positions=[
            AnonymizedPosition(
                ticker="AAPL",
                name="Apple Inc.",
                weight=Decimal("0.5"),
                currency=Currency.USD,
            ),
            AnonymizedPosition(
                ticker="MSFT",
                name="Microsoft Corporation",
                weight=Decimal("0.3"),
                currency=Currency.USD,
            ),
            AnonymizedPosition(
                ticker="GOOGL",
                name="Alphabet Inc.",
                weight=Decimal("0.2"),
                currency=Currency.USD,
            ),
        ],
    )


def test_gemini_service_initialization() -> None:
    """Test that GeminiAIService initializes correctly."""
    # Test with explicit API key
    service = GeminiAIService(api_key="test-key")
    assert service.api_key == "test-key"

    # Test without API key - should be None when no environment variable is set
    with (
        patch.dict(os.environ, {}, clear=True),
        patch("portfolio_assistant.services.ai.gemini.get_settings") as mock_settings,
    ):
        mock_settings.return_value.gemini_api_key = None
        service_no_key = GeminiAIService()
        assert service_no_key.api_key is None


@pytest.mark.asyncio
async def test_analyze_portfolio_missing_api_key(
    sample_portfolio: AnonymizedPortfolio,
) -> None:
    """Test that service returns appropriate message when API key is missing."""
    # Ensure no API key in environment and mock settings
    with (
        patch.dict(os.environ, {}, clear=True),
        patch("portfolio_assistant.services.ai.gemini.get_settings") as mock_settings,
    ):
        mock_settings.return_value.gemini_api_key = None
        service = GeminiAIService()
        result = await service.analyze_portfolio(sample_portfolio)

        expected_message = (
            "AI Analysis is currently unavailable because the Gemini API key "
            "is not configured."
        )
        assert result == expected_message


@pytest.mark.asyncio
async def test_analyze_portfolio_success(sample_portfolio: AnonymizedPortfolio) -> None:
    """Test successful API interaction and response rendering."""
    # Mock the async client and response
    mock_response = MagicMock()
    mock_response.text = "This is a test AI analysis in Czech."

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    with (
        patch("google.genai.Client", return_value=mock_client),
        patch("portfolio_assistant.services.ai.gemini.get_settings") as mock_settings,
    ):
        # Mock settings to return the expected model name
        mock_settings.return_value.gemini_model = "gemini-2.5-flash"

        service = GeminiAIService(api_key="test-key")
        result = await service.analyze_portfolio(sample_portfolio)

        # Verify the result contains the expected analysis
        assert result == "This is a test AI analysis in Czech."

        # Verify the client was called with correct parameters
        mock_client.aio.models.generate_content.assert_called_once()
        call_args = mock_client.aio.models.generate_content.call_args

        # Model name should be the one we mocked
        assert call_args[1]["model"] == "gemini-2.5-flash"
        assert "- AAPL (Apple Inc.): 50.00%" in call_args[1]["contents"]
        assert "- MSFT (Microsoft Corporation): 30.00%" in call_args[1]["contents"]
        assert "- GOOGL (Alphabet Inc.): 20.00%" in call_args[1]["contents"]


@pytest.mark.asyncio
async def test_analyze_portfolio_client_error(
    sample_portfolio: AnonymizedPortfolio,
) -> None:
    """Test graceful handling of ClientError."""
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=Exception("API error")
    )

    with patch("google.genai.Client", return_value=mock_client):
        service = GeminiAIService(api_key="test-key")
        result = await service.analyze_portfolio(sample_portfolio)

        expected_message = (
            "AI Analysis is currently unavailable due to an external service error."
        )
        assert result == expected_message


@pytest.mark.asyncio
async def test_analyze_portfolio_server_error(
    sample_portfolio: AnonymizedPortfolio,
) -> None:
    """Test graceful handling of ServerError."""
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=Exception("Server error")
    )

    with patch("google.genai.Client", return_value=mock_client):
        service = GeminiAIService(api_key="test-key")
        result = await service.analyze_portfolio(sample_portfolio)

        expected_message = (
            "AI Analysis is currently unavailable due to an external service error."
        )
        assert result == expected_message


@pytest.mark.asyncio
async def test_analyze_portfolio_generic_exception(
    sample_portfolio: AnonymizedPortfolio,
) -> None:
    """Test graceful handling of generic exceptions."""
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=Exception("Unexpected error")
    )

    with patch("google.genai.Client", return_value=mock_client):
        service = GeminiAIService(api_key="test-key")
        result = await service.analyze_portfolio(sample_portfolio)

        expected_message = (
            "AI Analysis is currently unavailable due to an external service error."
        )
        assert result == expected_message


@pytest.mark.asyncio
async def test_analyze_portfolio_empty_response(
    sample_portfolio: AnonymizedPortfolio,
) -> None:
    """Test handling of empty response from API."""
    mock_response = MagicMock()
    mock_response.text = None

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    with patch("google.genai.Client", return_value=mock_client):
        service = GeminiAIService(api_key="test-key")
        result = await service.analyze_portfolio(sample_portfolio)

        # Should return empty string when response.text is None
        assert result == ""


@pytest.mark.asyncio
async def test_analyze_portfolio_with_env_api_key(
    sample_portfolio: AnonymizedPortfolio,
) -> None:
    """Test that service uses environment variable
    when no explicit API key is provided."""
    mock_response = MagicMock()
    mock_response.text = "Analysis using env API key"

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    with patch.dict(os.environ, {"GEMINI_API_KEY": "env-test-key"}):
        # Clear cache so GitHub tests don't fall
        get_settings.cache_clear()

        with patch("google.genai.Client", return_value=mock_client):
            service = GeminiAIService()  # No explicit API key
            result = await service.analyze_portfolio(sample_portfolio)

            assert result == "Analysis using env API key"
            # Verify client was initialized (would use env var)
            mock_client.aio.models.generate_content.assert_called_once()

    # Clear one more time for the remaining tests
    get_settings.cache_clear()
