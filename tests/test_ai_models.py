"""Tests for timezone-safe AI persistence models."""

from datetime import UTC, datetime, timedelta

from portfolio_assistant.models.ai import ChatMessage, PortfolioAnalysis
from portfolio_assistant.services.ai_analysis import AIAnalysisService


def test_ai_models_default_to_utc_aware_timestamps() -> None:
    """Create AI records with UTC-aware default timestamps."""
    analysis = PortfolioAnalysis(
        portfolio_id=1,
        rating_score=80,
        analysis_content="Balanced portfolio.",
    )
    message = ChatMessage(portfolio_id=1, role="user", content="How is my risk?")

    assert analysis.created_at.tzinfo is UTC
    assert message.created_at.tzinfo is UTC


def test_analysis_cooldown_normalizes_naive_sqlite_timestamps() -> None:
    """Calculate cooldowns correctly for legacy naive SQLite timestamps."""
    analysis = PortfolioAnalysis(
        portfolio_id=1,
        rating_score=80,
        analysis_content="Balanced portfolio.",
        created_at=(datetime.now(UTC) - timedelta(minutes=1)).replace(tzinfo=None),
    )

    remaining = AIAnalysisService._get_remaining_cooldown(analysis)

    assert remaining is not None
