"""Persona-aware portfolio analysis generation and cache validation."""

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlmodel import Session, select

from portfolio_assistant.core.exceptions import AIAnalysisError
from portfolio_assistant.core.utils import get_now_utc
from portfolio_assistant.crud import ai_analysis as ai_analysis_crud
from portfolio_assistant.models.ai import (
    AIAnalysisRequest,
    AIAnalysisResponse,
    PortfolioAIAnalysis,
)
from portfolio_assistant.models.db_models import Portfolio, Position
from portfolio_assistant.models.persona import PERSONA_SYSTEM_PROMPTS, InvestmentPersona
from portfolio_assistant.services.ai.gemini import GeminiAIService

ANALYSIS_CACHE_TTL = timedelta(days=7)


class AIAnalysisService:
    """Generate persona-aware reports while safely reusing valid cached reports."""

    def __init__(self, gemini_service: GeminiAIService | None = None) -> None:
        self._gemini_service = gemini_service or GeminiAIService()

    async def get_or_generate_analysis(
        self,
        session: Session,
        portfolio_id: int,
        request: AIAnalysisRequest,
    ) -> AIAnalysisResponse:
        """Return a valid cached report or generate and persist a new report."""
        persona = self._parse_persona(request.persona_id)
        portfolio_hash, positions = self._get_portfolio_snapshot(session, portfolio_id)
        cached = ai_analysis_crud.get_latest_ai_analysis(session, portfolio_id)
        if cached is not None and self._is_cache_valid(
            cached,
            request,
            portfolio_hash,
        ):
            return AIAnalysisResponse(
                analysis_text=cached.analysis_text,
                persona_id=cached.persona_id,
                cached=True,
                created_at=self._as_utc(cached.created_at),
            )

        prompt = self._build_prompt(
            PERSONA_SYSTEM_PROMPTS[persona], positions, request.user_context
        )
        try:
            text = await self._gemini_service.generate_report(prompt)
        except RuntimeError as error:
            raise AIAnalysisError(str(error)) from error
        saved = ai_analysis_crud.save_ai_analysis(
            session,
            portfolio_id,
            text,
            persona.value,
            request.user_context,
            portfolio_hash,
        )
        return AIAnalysisResponse(
            analysis_text=saved.analysis_text,
            persona_id=saved.persona_id,
            cached=False,
            created_at=self._as_utc(saved.created_at),
        )

    async def generate_all_portfolios_analysis(
        self,
        session: Session,
        user_id: int,
        request: AIAnalysisRequest,
    ) -> AIAnalysisResponse:
        """Generate one report from every portfolio owned by the user."""
        persona = self._parse_persona(request.persona_id)
        positions = session.exec(
            select(Position).join(Portfolio).where(Portfolio.user_id == user_id)
        ).all()
        _, snapshot = self._get_positions_snapshot(positions)
        prompt = self._build_prompt(
            PERSONA_SYSTEM_PROMPTS[persona], snapshot, request.user_context
        )
        try:
            text = await self._gemini_service.generate_report(prompt)
        except RuntimeError as error:
            raise AIAnalysisError(str(error)) from error
        return AIAnalysisResponse(
            analysis_text=text,
            persona_id=persona.value,
            cached=False,
            created_at=get_now_utc(),
        )

    @staticmethod
    def _parse_persona(persona_id: str) -> InvestmentPersona:
        """Validate and normalize a requested persona identifier."""
        try:
            return InvestmentPersona(persona_id)
        except ValueError as error:
            allowed = ", ".join(persona.value for persona in InvestmentPersona)
            message = f"Unsupported persona_id. Allowed values: {allowed}."
            raise AIAnalysisError(message) from error

    @staticmethod
    def _get_portfolio_snapshot(
        session: Session,
        portfolio_id: int,
    ) -> tuple[str, list[dict[str, str]]]:
        """Return deterministic active-position data and its SHA256 hash."""
        positions = session.exec(
            select(Position).where(Position.portfolio_id == portfolio_id)
        ).all()
        return AIAnalysisService._get_positions_snapshot(positions)

    @staticmethod
    def _get_positions_snapshot(
        positions: Sequence[Position],
    ) -> tuple[str, list[dict[str, str]]]:
        """Serialize positions and return a deterministic cache hash."""
        active_positions = [position for position in positions if position.quantity > 0]
        total_value = sum(
            (position.quantity * position.unit_cost for position in active_positions),
            Decimal("0"),
        )
        snapshot = [
            AIAnalysisService._position_snapshot(position, total_value)
            for position in active_positions
        ]
        snapshot.sort(
            key=lambda item: (item["ticker"], item["isin"], item["asset_name"])
        )
        payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
        portfolio_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return portfolio_hash, snapshot

    @staticmethod
    def _position_snapshot(
        position: Position,
        total_value: Decimal,
    ) -> dict[str, str]:
        """Serialize one position with a Decimal-derived cost-basis weight."""
        value = position.quantity * position.unit_cost
        weight = value / total_value if total_value else Decimal("0")
        return {
            "asset_name": position.asset_name,
            "isin": position.isin or "",
            "quantity": str(position.quantity),
            "ticker": position.ticker,
            "weight": str(weight),
        }

    @staticmethod
    def _is_cache_valid(
        cached: PortfolioAIAnalysis | None,
        request: AIAnalysisRequest,
        portfolio_hash: str,
    ) -> bool:
        """Return whether the cached report exactly matches the request state."""
        if cached is None or request.force_refresh:
            return False
        created_at = AIAnalysisService._as_utc(cached.created_at)
        return (
            get_now_utc() - created_at < ANALYSIS_CACHE_TTL
            and cached.persona_id == request.persona_id
            and cached.user_context == request.user_context
            and cached.portfolio_hash == portfolio_hash
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        """Normalize legacy naive SQLite timestamps to UTC-aware datetimes."""
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value

    @staticmethod
    def _build_prompt(
        system_prompt: str,
        positions: list[dict[str, str]],
        user_context: str | None,
    ) -> str:
        """Build the complete model prompt from persona and portfolio context."""
        positions_text = (
            "\n".join(
                "- {ticker} ({asset_name}), ISIN: {isin}, weight: {weight}".format(
                    **position
                )
                for position in positions
            )
            or "No active positions are available."
        )
        context = user_context.strip() if user_context else "No user context supplied."
        return (
            f"System instructions:\n{system_prompt}\n\n"
            f"Portfolio positions:\n{positions_text}\n\n"
            f"Investor context:\n{context}\n\n"
            "Return only the requested Markdown report."
        )
