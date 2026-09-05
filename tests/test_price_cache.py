"""Tests for the database-backed current price cache service."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from sqlmodel import Session

from portfolio_assistant.core.utils import get_now_utc
from portfolio_assistant.crud.ticker_price import find_ticker_price, save_ticker_price
from portfolio_assistant.services.price_cache import PriceCacheService


def test_get_current_prices_uses_fresh_database_cache(db_session: Session) -> None:
    """Return a fresh database cache entry without contacting Yahoo Finance."""
    save_ticker_price(db_session, "AAPL", Decimal("120.00"))

    with patch("portfolio_assistant.services.price_cache.yf.Ticker") as ticker:
        prices = PriceCacheService.get_current_prices(db_session, ["AAPL"])

    assert prices == {"AAPL": Decimal("120.00")}
    ticker.assert_not_called()


def test_get_current_prices_refreshes_expired_price(db_session: Session) -> None:
    """Fetch and persist an updated price after cache expiry."""
    saved = save_ticker_price(db_session, "AAPL", Decimal("120.00"))
    saved.updated_at = get_now_utc() - timedelta(minutes=16)
    db_session.add(saved)
    db_session.commit()
    yahoo_ticker = MagicMock()
    yahoo_ticker.fast_info.get.return_value = 123.45

    with patch(
        "portfolio_assistant.services.price_cache.yf.Ticker",
        return_value=yahoo_ticker,
    ):
        prices = PriceCacheService.get_current_prices(db_session, ["AAPL"])

    cached = find_ticker_price(db_session, "AAPL")
    assert prices == {"AAPL": Decimal("123.45")}
    assert cached is not None
    assert cached.price == Decimal("123.45")


def test_get_current_prices_uses_expired_value_after_failure(
    db_session: Session,
) -> None:
    """Keep the last database price when Yahoo Finance is unavailable."""
    saved = save_ticker_price(db_session, "AAPL", Decimal("120.00"))
    saved.updated_at = get_now_utc() - timedelta(minutes=16)
    db_session.add(saved)
    db_session.commit()

    with patch(
        "portfolio_assistant.services.price_cache.yf.Ticker",
        side_effect=RuntimeError("network unavailable"),
    ):
        prices = PriceCacheService.get_current_prices(db_session, ["AAPL", "MSFT"])

    assert prices == {"AAPL": Decimal("120.00"), "MSFT": Decimal("0.00")}
