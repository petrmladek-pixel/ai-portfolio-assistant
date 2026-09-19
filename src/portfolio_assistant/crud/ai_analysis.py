"""Stateless database operations for persona-aware AI analysis reports."""

from sqlmodel import Session, col, select

from portfolio_assistant.models.ai import PortfolioAIAnalysis


def get_latest_ai_analysis(
    session: Session,
    portfolio_id: int,
) -> PortfolioAIAnalysis | None:
    """Return the newest persona-aware analysis for a portfolio."""
    statement = (
        select(PortfolioAIAnalysis)
        .where(PortfolioAIAnalysis.portfolio_id == portfolio_id)
        .order_by(col(PortfolioAIAnalysis.created_at).desc())
    )
    return session.exec(statement).first()


def save_ai_analysis(
    session: Session,
    portfolio_id: int,
    text: str,
    persona_id: str,
    user_context: str | None,
    portfolio_hash: str,
) -> PortfolioAIAnalysis:
    """Persist one persona-aware Markdown analysis report."""
    analysis = PortfolioAIAnalysis(
        portfolio_id=portfolio_id,
        analysis_text=text,
        persona_id=persona_id,
        user_context=user_context,
        portfolio_hash=portfolio_hash,
    )
    session.add(analysis)
    session.commit()
    session.refresh(analysis)
    return analysis
