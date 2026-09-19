"""Tests for persona-aware portfolio AI analysis caching."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from portfolio_assistant.models.ai import AIAnalysisRequest, PortfolioAIAnalysis
from portfolio_assistant.models.db_models import Portfolio, Position
from portfolio_assistant.models.user import User
from portfolio_assistant.services.ai_analysis_service import AIAnalysisService


@pytest.fixture
def portfolio_with_position(db_session):
    """Create a portfolio with one active position for cache tests."""
    user = User(email="analysis@example.com", hashed_password="hash")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    portfolio = Portfolio(
        name="Test portfolio",
        broker="Test broker",
        user_id=user.id,
    )
    db_session.add(portfolio)
    db_session.commit()
    db_session.refresh(portfolio)
    position = Position(
        asset_name="Apple Inc.",
        ticker="AAPL",
        currency="USD",
        quantity=Decimal("2"),
        unit_cost=Decimal("100"),
        acquisition_date=date(2025, 1, 1),
        portfolio_id=portfolio.id,
    )
    db_session.add(position)
    db_session.commit()
    return portfolio, position


@pytest.mark.asyncio
async def test_all_portfolios_analysis_uses_positions_from_each_owned_portfolio(
    db_session,
    portfolio_with_position,
) -> None:
    """Build an aggregate report from all portfolios belonging to one user."""
    portfolio, _ = portfolio_with_position
    second = Portfolio(
        name="Second portfolio",
        broker="Test broker",
        user_id=portfolio.user_id,
    )
    db_session.add(second)
    db_session.commit()
    db_session.refresh(second)
    db_session.add(
        Position(
            asset_name="Microsoft Corp.",
            ticker="MSFT",
            currency="USD",
            quantity=Decimal("1"),
            unit_cost=Decimal("200"),
            acquisition_date=date(2025, 1, 1),
            portfolio_id=second.id,
        )
    )
    db_session.commit()
    gemini = AsyncMock()
    gemini.generate_report.return_value = "# Combined report"
    service = AIAnalysisService(gemini_service=gemini)

    response = await service.generate_all_portfolios_analysis(
        db_session,
        portfolio.user_id,
        AIAnalysisRequest(),
    )

    assert response.cached is False
    prompt = gemini.generate_report.await_args.args[0]
    assert "AAPL" in prompt
    assert "MSFT" in prompt


@pytest.mark.asyncio
async def test_analysis_cache_hit_when_request_and_positions_match(
    db_session,
    portfolio_with_position,
) -> None:
    """Reuse a report only when every cache key matches."""
    portfolio, _ = portfolio_with_position
    gemini = AsyncMock()
    gemini.generate_report.return_value = "# Report"
    service = AIAnalysisService(gemini_service=gemini)
    request = AIAnalysisRequest(user_context="I am investing for retirement.")

    first = await service.get_or_generate_analysis(db_session, portfolio.id, request)
    second = await service.get_or_generate_analysis(db_session, portfolio.id, request)

    assert first.cached is False
    assert second.cached is True
    assert gemini.generate_report.await_count == 1
    assert second.created_at.tzinfo is UTC


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changed_request",
    [
        AIAnalysisRequest(user_context="I intend to rotate into bonds."),
        AIAnalysisRequest(persona_id="GROWTH"),
    ],
)
async def test_analysis_cache_invalidates_for_changed_request(
    db_session,
    portfolio_with_position,
    changed_request: AIAnalysisRequest,
) -> None:
    """Regenerate when persona or user context differs from the cached request."""
    portfolio, _ = portfolio_with_position
    gemini = AsyncMock()
    gemini.generate_report.return_value = "# Fresh report"
    service = AIAnalysisService(gemini_service=gemini)
    original = AIAnalysisRequest(user_context="I invest for retirement.")

    await service.get_or_generate_analysis(db_session, portfolio.id, original)
    response = await service.get_or_generate_analysis(
        db_session,
        portfolio.id,
        changed_request,
    )

    assert response.cached is False
    assert gemini.generate_report.await_count == 2


@pytest.mark.asyncio
async def test_analysis_cache_invalidates_when_refresh_is_forced(
    db_session,
    portfolio_with_position,
) -> None:
    """Bypass an otherwise valid cache entry when the caller requests it."""
    portfolio, _ = portfolio_with_position
    gemini = AsyncMock()
    gemini.generate_report.return_value = "# Fresh report"
    service = AIAnalysisService(gemini_service=gemini)
    request = AIAnalysisRequest()

    await service.get_or_generate_analysis(db_session, portfolio.id, request)
    response = await service.get_or_generate_analysis(
        db_session,
        portfolio.id,
        AIAnalysisRequest(force_refresh=True),
    )

    assert response.cached is False
    assert gemini.generate_report.await_count == 2


@pytest.mark.asyncio
async def test_analysis_cache_invalidates_when_positions_change(
    db_session,
    portfolio_with_position,
) -> None:
    """Regenerate after a holding changes because the portfolio hash changes."""
    portfolio, position = portfolio_with_position
    gemini = AsyncMock()
    gemini.generate_report.return_value = "# Fresh report"
    service = AIAnalysisService(gemini_service=gemini)
    request = AIAnalysisRequest()

    await service.get_or_generate_analysis(db_session, portfolio.id, request)
    position.quantity = Decimal("3")
    db_session.add(position)
    db_session.commit()
    response = await service.get_or_generate_analysis(db_session, portfolio.id, request)

    assert response.cached is False
    assert gemini.generate_report.await_count == 2


def test_cache_validity_normalizes_naive_sqlite_datetime() -> None:
    """Treat legacy SQLite timestamps as UTC before evaluating their age."""
    cached = PortfolioAIAnalysis(
        portfolio_id=1,
        analysis_text="# Report",
        portfolio_hash="hash",
        created_at=(datetime.now(UTC) - timedelta(minutes=1)).replace(tzinfo=None),
    )

    assert AIAnalysisService._is_cache_valid(
        cached,
        AIAnalysisRequest(),
        "hash",
    )
