"""Database operations for ticker metadata caching."""

from datetime import UTC, datetime

from sqlmodel import Session, select

from portfolio_assistant.models.ticker_metadata import TickerMetadata


def get_ticker_metadata(db: Session, ticker: str) -> TickerMetadata | None:
    """Return ticker metadata for the given ticker, if it exists."""
    statement = select(TickerMetadata).where(TickerMetadata.ticker == ticker)
    return db.exec(statement).first()


def save_ticker_metadata(
    db: Session, ticker: str, sector: str, country: str
) -> TickerMetadata:
    """Save or update ticker metadata with upsert logic."""
    metadata = get_ticker_metadata(db, ticker)
    current_time = datetime.now(UTC)
    if metadata:
        metadata.sector = sector
        metadata.country = country
        metadata.updated_at = current_time
        db.add(metadata)
    else:
        metadata = TickerMetadata(
            ticker=ticker,
            sector=sector,
            country=country,
            updated_at=current_time,
        )
        db.add(metadata)
    db.commit()
    db.refresh(metadata)
    return metadata
