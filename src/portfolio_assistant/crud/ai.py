"""Stateless database operations for cached AI portfolio analyses."""

from sqlmodel import Session, col, select

from portfolio_assistant.models.ai import PortfolioAnalysis


def get_latest_analysis(db: Session, portfolio_id: int) -> PortfolioAnalysis | None:
    """Return the newest cached analysis for a portfolio, if present."""
    statement = (
        select(PortfolioAnalysis)
        .where(PortfolioAnalysis.portfolio_id == portfolio_id)
        .order_by(col(PortfolioAnalysis.created_at).desc())
    )
    return db.exec(statement).first()


def save_analysis(
    db: Session,
    portfolio_id: int,
    rating: int,
    content: str,
) -> PortfolioAnalysis:
    """Persist and refresh one generated portfolio analysis."""
    analysis = PortfolioAnalysis(
        portfolio_id=portfolio_id,
        rating_score=rating,
        analysis_content=content,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis
