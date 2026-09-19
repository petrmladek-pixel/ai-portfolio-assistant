"""Business workflow for generating and caching Gemini portfolio analyses."""

import json
import re
from datetime import UTC, timedelta
from pathlib import Path
from typing import Any

from google import genai
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from portfolio_assistant.config import get_settings
from portfolio_assistant.core.exceptions import (
    AIAnalysisError,
    PersistenceError,
    PortfolioNotFoundError,
)
from portfolio_assistant.core.utils import get_now_utc
from portfolio_assistant.crud import ai as ai_crud
from portfolio_assistant.crud import portfolio as portfolio_crud
from portfolio_assistant.models.ai import PortfolioAnalysis
from portfolio_assistant.models.allocation import PortfolioAllocationResponse
from portfolio_assistant.models.user import User
from portfolio_assistant.services.allocation import AllocationService

ANALYSIS_COOLDOWN = timedelta(days=7)
_DEFAULT_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "default_analysis.md"
)
DEFAULT_ANALYSIS_PROMPT = _DEFAULT_PROMPT_PATH.read_text(encoding="utf-8").strip()


class AnalysisCooldownError(ValueError):
    """Raised when a portfolio has a recent cached AI analysis."""

    def __init__(
        self,
        cached_analysis: PortfolioAnalysis,
        remaining_time: timedelta,
    ) -> None:
        self.cached_analysis = cached_analysis
        self.remaining_time = remaining_time
        super().__init__("AI analysis cooldown is active.")


class AIAnalysisService:
    """Coordinate allocation data, Gemini generation, and analysis caching."""

    def __init__(
        self,
        allocation_service: AllocationService | None = None,
        client: Any | None = None,
    ) -> None:
        settings = get_settings()
        self._allocation_service = allocation_service or AllocationService()
        self._model = settings.gemini_model
        self._client = client
        if self._client is None and settings.gemini_api_key:
            self._client = genai.Client(api_key=settings.gemini_api_key)

    async def analyze_portfolio(
        self,
        db: Session,
        portfolio_id: int,
        user: User,
    ) -> PortfolioAnalysis:
        """Create an analysis unless a valid cached report is still cooling down."""
        self._ensure_owned_portfolio(db, portfolio_id, user)
        latest_analysis = ai_crud.get_latest_analysis(db, portfolio_id)
        if latest_analysis is not None:
            remaining_time = self._get_remaining_cooldown(latest_analysis)
            if remaining_time is not None:
                raise AnalysisCooldownError(latest_analysis, remaining_time)

        allocations = await self._allocation_service.calculate_portfolio_allocations(
            db, portfolio_id=portfolio_id
        )
        response_text = await self._generate_analysis(
            self._build_prompt(allocations, user.analysis_prompt)
        )
        rating, content = self._parse_response(response_text)
        try:
            return ai_crud.save_analysis(db, portfolio_id, rating, content)
        except SQLAlchemyError as error:
            db.rollback()
            raise PersistenceError from error

    def get_latest_analysis(
        self,
        db: Session,
        portfolio_id: int,
        user: User,
    ) -> PortfolioAnalysis | None:
        """Return the latest cached analysis for an owned portfolio."""
        self._ensure_owned_portfolio(db, portfolio_id, user)
        return ai_crud.get_latest_analysis(db, portfolio_id)

    @staticmethod
    def _ensure_owned_portfolio(db: Session, portfolio_id: int, user: User) -> None:
        """Ensure the supplied portfolio belongs to the requesting user."""
        if user.id is None:
            raise PortfolioNotFoundError
        portfolio = portfolio_crud.get_portfolio_for_user(db, portfolio_id, user.id)
        if portfolio is None:
            raise PortfolioNotFoundError

    @staticmethod
    def _get_remaining_cooldown(
        analysis: PortfolioAnalysis,
    ) -> timedelta | None:
        """Return remaining cooldown duration when the analysis remains current."""
        created_at = analysis.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        remaining_time = ANALYSIS_COOLDOWN - (get_now_utc() - created_at)
        return remaining_time if remaining_time > timedelta() else None

    async def _generate_analysis(self, prompt: str) -> str:
        """Request a structured portfolio analysis from Gemini."""
        if self._client is None:
            raise AIAnalysisError("Gemini API key is not configured.")
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
            )
        except Exception as error:
            raise AIAnalysisError("Gemini analysis request failed.") from error
        response_text = getattr(response, "text", None)
        if not isinstance(response_text, str) or not response_text.strip():
            raise AIAnalysisError("Gemini returned an empty analysis response.")
        return response_text.strip()

    @staticmethod
    def _build_prompt(
        allocations: PortfolioAllocationResponse,
        custom_prompt: str | None,
    ) -> str:
        """Build the Gemini prompt from allocation metrics and user guidance."""
        user_prompt = custom_prompt.strip() if custom_prompt else ""
        instructions = user_prompt or DEFAULT_ANALYSIS_PROMPT
        positions = "\n".join(
            "- {ticker}: {percentage:.2f}% | value: {value} CZK | "
            "sector: {sector} | region: {region}".format(
                ticker=item.ticker,
                percentage=item.percentage,
                value=item.market_value,
                sector=item.sector or "Unknown",
                region=item.region or "Unknown",
            )
            for item in allocations.allocations
        )
        if not positions:
            positions = "No active positions are available."
        return (
            "You are a careful portfolio-analysis assistant. Your output is "
            "educational only and must not be investment advice.\n\n"
            f"Portfolio total value: {allocations.total_value} CZK\n"
            f"Portfolio positions:\n{positions}\n\n"
            f"User instructions:\n{instructions}\n\n"
            "Return valid JSON only, with this exact schema: "
            '{"rating_score": 1, "analysis_report": "Markdown report"}. '
            "rating_score must be an integer from 1 through 100."
        )

    @staticmethod
    def _parse_response(response_text: str) -> tuple[int, str]:
        """Extract and validate the rating and Markdown report from Gemini output."""
        data = AIAnalysisService._parse_json_response(response_text)
        if data is not None:
            rating = data.get("rating_score")
            content = data.get("analysis_report", data.get("analysis"))
            if isinstance(rating, int) and isinstance(content, str) and content.strip():
                if 1 <= rating <= 100:
                    return rating, content.strip()

        match = re.search(
            r"(?:rating_score|rating\\s*score)\s*[:=-]\s*(\d{1,3})",
            response_text,
            flags=re.IGNORECASE,
        )
        if match is not None:
            rating = int(match.group(1))
            if 1 <= rating <= 100:
                return rating, response_text.strip()
        raise AIAnalysisError(
            "Gemini response did not contain a valid rating and report."
        )

    @staticmethod
    def _parse_json_response(response_text: str) -> dict[str, Any] | None:
        """Parse a JSON object, including one optionally wrapped in a code fence."""
        cleaned = response_text.strip()
        if cleaned.startswith("```") and cleaned.endswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None
