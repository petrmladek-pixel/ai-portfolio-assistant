"""Tests for portfolio allocation calculations."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import Session

from portfolio_assistant.models.db_models import Position
from portfolio_assistant.services.allocation import AllocationService


@pytest.mark.asyncio
async def test_calculate_portfolio_allocations(db_session: Session) -> None:
    """Calculate holdings, values, and allocation percentages from positions."""
    db_session.add_all(
        [
            Position(
                asset_name="Apple Inc.",
                ticker="AAPL",
                currency="USD",
                quantity=Decimal("3"),
                unit_cost=Decimal("90"),
                acquisition_date=date(2025, 1, 1),
                portfolio_id=4,
            ),
            Position(
                asset_name="Microsoft Corp.",
                ticker="MSFT",
                currency="USD",
                quantity=Decimal("1"),
                unit_cost=Decimal("150"),
                acquisition_date=date(2025, 1, 1),
                portfolio_id=4,
            ),
            Position(
                asset_name="Cash",
                ticker="CASH",
                currency="USD",
                quantity=Decimal("50"),
                unit_cost=Decimal("1"),
                acquisition_date=date(2025, 1, 1),
                portfolio_id=4,
            ),
            Position(
                asset_name="Tesla Inc.",
                ticker="TSLA",
                currency="USD",
                quantity=Decimal("1"),
                unit_cost=Decimal("180"),
                acquisition_date=date(2025, 1, 1),
                portfolio_id=7,
            ),
        ]
    )
    db_session.flush()

    with (
        patch(
            "portfolio_assistant.services.allocation."
            "PriceCacheService.get_current_prices",
            return_value={
                "AAPL": Decimal("100"),
                "MSFT": Decimal("200"),
                "TSLA": Decimal("100"),
            },
        ),
        patch(
            "portfolio_assistant.services.allocation."
            "MetadataCacheService.get_tickers_metadata",
            return_value={
                "AAPL": {"sector": "Technology", "country": "United States"},
            },
        ),
        patch(
            "portfolio_assistant.services.allocation."
            "YFinanceMarketDataService.get_exchange_rate",
            new_callable=AsyncMock,
            return_value=Decimal("1"),
        ),
    ):
        response = await AllocationService().calculate_portfolio_allocations(
            session=db_session,
            portfolio_id=4,
        )
        all_response = await AllocationService().calculate_portfolio_allocations(
            session=db_session,
        )

    assert response.total_value == Decimal("550")
    assert response.allocations[0].ticker == "AAPL"
    assert response.allocations[0].quantity == Decimal("3")
    assert response.allocations[0].percentage == Decimal(
        "54.54545454545454545454545455"
    )
    assert response.allocations[0].sector == "Technology"
    assert response.allocations[0].region == "United States"
    assert response.allocations[1].percentage == Decimal(
        "36.36363636363636363636363636"
    )
    assert response.allocations[1].sector == "Unknown"
    assert response.allocations[1].region == "Unknown"
    assert response.allocations[2].ticker == "CASH"
    assert response.allocations[2].percentage == Decimal(
        "9.090909090909090909090909091"
    )
    assert response.allocations[2].sector == "Cash"
    assert response.allocations[2].region == "Cash"
    assert all_response.portfolio_id is None
    assert all_response.total_value == Decimal("650")
    assert len(all_response.allocations) == 4


@pytest.mark.asyncio
async def test_calculate_portfolio_allocations_returns_empty_for_zero_value(
    db_session: Session,
) -> None:
    """Return no allocations when a portfolio has no positive-valued holdings."""
    with (
        patch(
            "portfolio_assistant.services.allocation."
            "PriceCacheService.get_current_prices",
            return_value={},
        ),
        patch(
            "portfolio_assistant.services.allocation."
            "MetadataCacheService.get_tickers_metadata",
            return_value={},
        ),
    ):
        response = await AllocationService().calculate_portfolio_allocations(
            session=db_session,
            portfolio_id=4,
        )

    assert response.total_value == Decimal("0.00")
    assert response.allocations == []


@pytest.mark.asyncio
async def test_calculate_portfolio_allocations_converts_to_czk(
    db_session: Session,
) -> None:
    """Convert foreign-currency position values before calculating weights."""
    db_session.add(
        Position(
            asset_name="US Asset",
            ticker="USASSET",
            currency="USD",
            quantity=Decimal("2"),
            unit_cost=Decimal("10"),
            acquisition_date=date(2025, 1, 1),
            portfolio_id=4,
        )
    )
    db_session.flush()

    with (
        patch(
            "portfolio_assistant.services.allocation."
            "PriceCacheService.get_current_prices",
            return_value={"USASSET": Decimal("10")},
        ),
        patch(
            "portfolio_assistant.services.allocation."
            "MetadataCacheService.get_tickers_metadata",
            return_value={},
        ),
        patch(
            "portfolio_assistant.services.allocation."
            "YFinanceMarketDataService.get_exchange_rate",
            new_callable=AsyncMock,
            return_value=Decimal("20"),
        ),
    ):
        response = await AllocationService().calculate_portfolio_allocations(
            session=db_session,
            portfolio_id=4,
        )

    assert response.total_value == Decimal("400")
    assert response.allocations[0].market_value == Decimal("400")
