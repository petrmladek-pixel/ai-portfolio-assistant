"""Gemini AI service for portfolio analysis.

This module provides asynchronous integration with Google's Gemini AI
for analyzing anonymized portfolio data.
"""

import logging

from google import genai

from portfolio_assistant.config import get_settings
from portfolio_assistant.models.portfolio import AnonymizedPortfolio

logger = logging.getLogger(__name__)

# Constants
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


class GeminiAIService:
    """Service for analyzing portfolios using Google Gemini AI.

    Attributes:
        api_key (Optional[str]): The Gemini API key. If not provided,
            the genai.Client will look for GEMINI_API_KEY in environment variables.
    """

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize the Gemini AI service.

        Args:
            api_key (Optional[str]): The Gemini API key. If None,
                the service will attempt to use the GEMINI_API_KEY
                environment variable via settings.
        """
        # Get settings once and use them for both API key and model configuration
        settings = get_settings()
        self.api_key = api_key or settings.gemini_api_key

        # Initialize client for connection pooling if API key is available
        self._client = genai.Client(api_key=self.api_key) if self.api_key else None

    async def analyze_portfolio(self, portfolio: AnonymizedPortfolio) -> str:
        """Analyze a portfolio using Gemini AI.

        Args:
            portfolio (AnonymizedPortfolio): The anonymized portfolio to analyze.

        Returns:
            str: The AI-generated analysis in Czech, or an error message if
                the analysis cannot be performed.
        """
        # Check if client is available (API key was configured)
        if not self._client:
            return (
                "AI Analysis is currently unavailable because the Gemini API key "
                "is not configured."
            )

        try:
            # Build the prompt with ticker symbols and percentage weights
            positions_text = "\n".join(
                f"- {pos.ticker} ({pos.name}): {pos.weight * 100:.2f}%"
                for pos in portfolio.positions
            )

            prompt = (
                "You are a professional financial advisor. Analyze the "
                "following investment portfolio and provide a "
                "comprehensive, high-quality evaluation.\n\n"
                "The portfolio contains the following positions (expressed "
                f"only in percentage weights):\n{positions_text}\n\n"
                "To accurately identify the assets and their profiles, always "
                "use the provided asset names in parentheses next to "
                "individual tickers.\n\n"
                "Perform a comprehensive analysis covering the following "
                "points:\n"
                "1. Diversification: Assess how the portfolio is distributed "
                "across different sectors and regions.\n"
                "2. Sector and Geographical Allocation: Estimate the "
                "allocation based on the provided asset names and tickers.\n"
                "3. Strengths and Potential Risks: Identify the key "
                "advantages and vulnerabilities of this allocation.\n"
                "4. Actionable Recommendations: Provide general, non-binding "
                "recommendations for improving the portfolio's balance.\n\n"
                "Formatting & Language Instructions:\n"
                "- Format the output as a professional report using clean "
                "Markdown (headings, bullet points, and bold text) suitable "
                "for rendering on a web dashboard.\n"
                "- At the very end, append a standard educational "
                "disclaimer stating that this analysis is informative only "
                "and does not constitute financial or investment advice.\n"
            )

            # Get model name from settings with fallback to constant
            settings = get_settings()
            model_name = settings.gemini_model or DEFAULT_GEMINI_MODEL

            # Use the pre-initialized client for connection pooling
            response = await self._client.aio.models.generate_content(
                model=model_name, contents=prompt
            )

            return response.text or ""

        except Exception:
            # Log the full exception stack trace safely for monitoring systems
            logger.exception("Gemini API call failed")
            return (
                "AI Analysis is currently unavailable due to an external service error."
            )
