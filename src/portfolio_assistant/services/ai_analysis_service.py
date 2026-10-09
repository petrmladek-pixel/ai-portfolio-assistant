"""User-owned strategic analysis generation and cache validation."""

import hashlib
import json
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, col, select

from portfolio_assistant.core.exceptions import AIAnalysisError
from portfolio_assistant.core.utils import get_now_utc
from portfolio_assistant.crud import ai_analysis as ai_analysis_crud
from portfolio_assistant.models.ai import (
    AIAnalysisRequest,
    AIAnalysisResponse,
    PortfolioAIAnalysis,
)
from portfolio_assistant.models.allocation import PortfolioAllocationResponse
from portfolio_assistant.models.db_models import Portfolio
from portfolio_assistant.models.persona import PERSONA_SYSTEM_PROMPTS, InvestmentPersona
from portfolio_assistant.services.ai.gemini import GeminiAIService
from portfolio_assistant.services.allocation import AllocationService

ANALYSIS_CACHE_TTL = timedelta(days=7)


class AIAnalysisService:
    """Generate cached strategic reports from current whole-wealth allocations."""

    def __init__(
        self,
        gemini_service: GeminiAIService | None = None,
        allocation_service: AllocationService | None = None,
    ) -> None:
        self._gemini_service = gemini_service or GeminiAIService()
        self._allocation_service = allocation_service or AllocationService()

    async def get_or_generate_analysis(
        self,
        session: Session,
        source_portfolio_id: int,
        request: AIAnalysisRequest,
        user_id: int | None = None,
    ) -> AIAnalysisResponse:
        """Return a valid wealth cache entry or generate one from market values."""
        user_id = user_id or self._get_user_id(session, source_portfolio_id)
        persona = self._parse_persona(request.persona_id)
        allocations = await self._allocation_service.calculate_portfolio_allocations(
            session,
            user_id=user_id,
        )
        allocation_hash, snapshot = self._get_allocation_snapshot(allocations)
        cached = ai_analysis_crud.get_latest_ai_analysis_for_user(session, user_id)
        if self._is_cache_valid(cached, request, allocation_hash):
            assert cached is not None
            return self._response_from_cached(cached)
        prompt = self._build_prompt(
            PERSONA_SYSTEM_PROMPTS[persona],
            snapshot,
            request.user_context,
        )
        try:
            text = await self._gemini_service.generate_report(prompt)
        except RuntimeError as error:
            raise AIAnalysisError(str(error)) from error
        saved = ai_analysis_crud.save_ai_analysis(
            session,
            source_portfolio_id,
            user_id,
            text,
            persona.value,
            request.user_context,
            allocation_hash,
        )
        return self._response_from_cached(saved, cache_hit=False)

    async def get_latest_cached_analysis(
        self,
        session: Session,
        user_id: int,
        user_context: str | None,
    ) -> AIAnalysisResponse | None:
        """Return the user's current wealth report without generating one."""
        cached = ai_analysis_crud.get_latest_ai_analysis_for_user(session, user_id)
        if cached is None:
            return None
        allocations = await self._allocation_service.calculate_portfolio_allocations(
            session,
            user_id=user_id,
        )
        allocation_hash, _ = self._get_allocation_snapshot(allocations)
        request = AIAnalysisRequest(
            persona_id=cached.persona_id,
            user_context=user_context,
        )
        if not self._is_cache_valid(cached, request, allocation_hash):
            return None
        return self._response_from_cached(cached)

    async def generate_all_portfolios_analysis(
        self,
        session: Session,
        user_id: int,
        request: AIAnalysisRequest,
    ) -> AIAnalysisResponse:
        """Generate the shared wealth report from the all-portfolios view."""
        return await self.get_or_generate_analysis(
            session,
            self._get_source_portfolio_id(session, user_id),
            request,
            user_id,
        )

    async def get_latest_all_portfolios_analysis(
        self,
        session: Session,
        user_id: int,
        user_context: str | None,
    ) -> AIAnalysisResponse | None:
        """Return the shared wealth report for the all-portfolios view."""
        return await self.get_latest_cached_analysis(session, user_id, user_context)

    @staticmethod
    def _get_source_portfolio_id(session: Session, user_id: int) -> int:
        """Return a portfolio only for the legacy foreign-key reference."""
        statement = select(Portfolio.id).where(Portfolio.user_id == user_id)
        portfolio_id = session.exec(statement.order_by(col(Portfolio.id))).first()
        if portfolio_id is None:
            raise AIAnalysisError("No portfolio is available for analysis.")
        return portfolio_id

    @staticmethod
    def _get_user_id(session: Session, portfolio_id: int) -> int:
        """Return the owner of a source portfolio for compatibility callers."""
        statement = select(Portfolio.user_id).where(Portfolio.id == portfolio_id)
        user_id = session.exec(statement).first()
        if user_id is None:
            raise AIAnalysisError("Portfolio owner is not available for analysis.")
        return user_id

    @staticmethod
    def _get_allocation_snapshot(
        allocations: PortfolioAllocationResponse,
    ) -> tuple[str, list[dict[str, str]]]:
        """Serialize current market allocations and return their cache hash."""
        snapshot = [
            {
                "market_value": str(item.market_value),
                "region": item.region or "Unknown",
                "sector": item.sector or "Unknown",
                "ticker": item.ticker,
                "weight": str(item.percentage / 100),
            }
            for item in allocations.allocations
        ]
        snapshot.sort(key=lambda item: item["ticker"])
        payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest(), snapshot

    @staticmethod
    def _parse_persona(persona_id: str) -> InvestmentPersona:
        """Validate and normalize a requested persona identifier."""
        try:
            return InvestmentPersona(persona_id)
        except ValueError as error:
            allowed = ", ".join(persona.value for persona in InvestmentPersona)
            raise AIAnalysisError(
                f"Unsupported persona_id. Allowed values: {allowed}."
            ) from error

    @staticmethod
    def _is_cache_valid(
        cached: PortfolioAIAnalysis | None,
        request: AIAnalysisRequest,
        allocation_hash: str,
    ) -> bool:
        """Return whether the cached report exactly matches current wealth data."""
        if cached is None or request.force_refresh:
            return False
        return (
            get_now_utc() - AIAnalysisService._as_utc(cached.created_at)
            < ANALYSIS_CACHE_TTL
            and cached.persona_id == request.persona_id
            and cached.user_context == request.user_context
            and cached.portfolio_hash == allocation_hash
        )

    @staticmethod
    def _response_from_cached(
        analysis: PortfolioAIAnalysis,
        cache_hit: bool = True,
    ) -> AIAnalysisResponse:
        """Map a database cache record to the public response model."""
        return AIAnalysisResponse(
            analysis_text=analysis.analysis_text,
            persona_id=analysis.persona_id,
            user_context=analysis.user_context,
            cached=cache_hit,
            created_at=AIAnalysisService._as_utc(analysis.created_at),
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        """Normalize legacy naive SQLite timestamps to UTC-aware datetimes."""
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value

    @staticmethod
    def _build_prompt(
        system_prompt: str,
        allocations: list[dict[str, str]],
        user_context: str | None,
    ) -> str:
        """Build the complete model prompt from market-valued wealth data."""
        positions_text = (
            "\n".join(
                "- {ticker}, weight: {weight}, value: {market_value}, "
                "sector: {sector}, region: {region}".format(**item)
                for item in allocations
            )
            or "No active positions are available."
        )
        context = user_context.strip() if user_context else "No user context supplied."
        return (
            f"System instructions:\n{system_prompt}\n\n"
            f"Current whole-wealth allocation:\n{positions_text}\n\n"
            f"Investor context:\n{context}\n\n"
            "Return only the requested Markdown report."
        )
