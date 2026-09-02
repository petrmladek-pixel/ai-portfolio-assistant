"""Tests for ticker metadata model and CRUD operations."""

from sqlmodel import Session

from portfolio_assistant.crud.ticker_metadata import (
    get_ticker_metadata,
    save_ticker_metadata,
)


def test_get_ticker_metadata_not_found(db_session: Session) -> None:
    """Test retrieving non-existent ticker metadata returns None."""
    result = get_ticker_metadata(db_session, "INVALID")
    assert result is None


def test_save_and_get_ticker_metadata(db_session: Session) -> None:
    """Test inserting and retrieving ticker metadata."""
    saved = save_ticker_metadata(
        db_session, "AAPL", sector="Technology", country="United States"
    )
    assert saved.ticker == "AAPL"
    assert saved.sector == "Technology"
    assert saved.country == "United States"
    assert saved.updated_at is not None

    retrieved = get_ticker_metadata(db_session, "AAPL")
    assert retrieved is not None
    assert retrieved.ticker == "AAPL"
    assert retrieved.sector == "Technology"
    assert retrieved.country == "United States"


def test_save_ticker_metadata_upsert(db_session: Session) -> None:
    """Test updating existing ticker metadata (upsert logic)."""
    first_save = save_ticker_metadata(db_session, "MSFT", sector="Tech", country="US")
    first_time = first_save.updated_at

    second_save = save_ticker_metadata(
        db_session, "MSFT", sector="Technology", country="United States"
    )
    assert second_save.sector == "Technology"
    assert second_save.country == "United States"
    assert second_save.updated_at >= first_time
