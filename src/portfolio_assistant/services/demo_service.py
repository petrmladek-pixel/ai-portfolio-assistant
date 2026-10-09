"""Service for the public and one-click Berkshire Hathaway demo portfolio."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from portfolio_assistant.config import get_settings
from portfolio_assistant.core.exceptions import PersistenceError
from portfolio_assistant.crud import portfolio as portfolio_crud
from portfolio_assistant.crud import user as user_crud
from portfolio_assistant.models.ai import AIAnalysisResponse
from portfolio_assistant.models.allocation import (
    AssetAllocation,
    PortfolioAllocationResponse,
)
from portfolio_assistant.models.db_models import Portfolio, Position
from portfolio_assistant.models.user import User

DEMO_PORTFOLIO_NAME = "Warren Buffett / Berkshire Hathaway Demo"
DEMO_BROKER = "Berkshire Hathaway"
DEMO_AI_ANALYSIS = (
    "# Berkshire Hathaway Demo Analysis\n\n"
    "This read-only demonstration illustrates a concentrated, quality-focused "
    "equity allocation. It is educational content, not investment advice."
)


@dataclass(frozen=True)
class _DemoPosition:
    name: str
    ticker: str
    isin: str
    unit_cost: Decimal
    target_value: Decimal
    sector: str
    region: str


_DEMO_POSITIONS = (
    _DemoPosition(
        "Apple Inc.",
        "AAPL",
        "US0378331005",
        Decimal("190"),
        Decimal("28000"),
        "Technology",
        "United States",
    ),
    _DemoPosition(
        "Bank of America Corporation",
        "BAC",
        "US0605051046",
        Decimal("40"),
        Decimal("11000"),
        "Financials",
        "United States",
    ),
    _DemoPosition(
        "American Express Company",
        "AXP",
        "US0258161092",
        Decimal("250"),
        Decimal("16000"),
        "Financials",
        "United States",
    ),
    _DemoPosition(
        "The Coca-Cola Company",
        "KO",
        "US1912161007",
        Decimal("70"),
        Decimal("9000"),
        "Consumer Staples",
        "United States",
    ),
    _DemoPosition(
        "Chevron Corporation",
        "CVX",
        "US1667641005",
        Decimal("150"),
        Decimal("5000"),
        "Energy",
        "United States",
    ),
    _DemoPosition(
        "Occidental Petroleum Corporation",
        "OXY",
        "US6745991058",
        Decimal("50"),
        Decimal("4500"),
        "Energy",
        "United States",
    ),
    _DemoPosition(
        "Moody's Corporation",
        "MCO",
        "US6153691059",
        Decimal("450"),
        Decimal("4000"),
        "Financials",
        "United States",
    ),
    _DemoPosition(
        "The Kraft Heinz Company",
        "KHC",
        "US5007541064",
        Decimal("30"),
        Decimal("3500"),
        "Consumer Staples",
        "United States",
    ),
    _DemoPosition(
        "DaVita Inc.",
        "DVA",
        "US23918K1088",
        Decimal("160"),
        Decimal("3000"),
        "Health Care",
        "United States",
    ),
    _DemoPosition(
        "Chubb Limited",
        "CB",
        "CH0044328745",
        Decimal("280"),
        Decimal("2800"),
        "Financials",
        "Switzerland",
    ),
    _DemoPosition(
        "Kroger Co.",
        "KR",
        "US5010441013",
        Decimal("55"),
        Decimal("2200"),
        "Consumer Staples",
        "United States",
    ),
    _DemoPosition(
        "VeriSign, Inc.",
        "VRSN",
        "US92343E1029",
        Decimal("220"),
        Decimal("2000"),
        "Technology",
        "United States",
    ),
    _DemoPosition(
        "Mastercard Incorporated",
        "MA",
        "US57636Q1040",
        Decimal("450"),
        Decimal("1800"),
        "Financials",
        "United States",
    ),
    _DemoPosition(
        "Visa Inc.",
        "V",
        "US92826C8394",
        Decimal("300"),
        Decimal("1600"),
        "Financials",
        "United States",
    ),
    _DemoPosition(
        "Sirius XM Holdings Inc.",
        "SIRI",
        "US82968B1035",
        Decimal("4"),
        Decimal("1400"),
        "Communication Services",
        "United States",
    ),
    _DemoPosition(
        "HP Inc.",
        "HPQ",
        "US40434L1052",
        Decimal("30"),
        Decimal("1200"),
        "Technology",
        "United States",
    ),
    _DemoPosition(
        "Louisiana-Pacific Corporation",
        "LPX",
        "US5463471053",
        Decimal("90"),
        Decimal("1100"),
        "Materials",
        "United States",
    ),
    _DemoPosition(
        "Capital One Financial Corporation",
        "COF",
        "US14040H1059",
        Decimal("180"),
        Decimal("1000"),
        "Financials",
        "United States",
    ),
    _DemoPosition(
        "Amazon.com, Inc.",
        "AMZN",
        "US0231351067",
        Decimal("200"),
        Decimal("900"),
        "Consumer Discretionary",
        "United States",
    ),
    _DemoPosition(
        "Nu Holdings Ltd.",
        "NU",
        "KYG6683N1034",
        Decimal("15"),
        Decimal("800"),
        "Financials",
        "Brazil",
    ),
    _DemoPosition(
        "Taiwan Semiconductor Manufacturing",
        "TSM",
        "US8740391003",
        Decimal("200"),
        Decimal("700"),
        "Technology",
        "Taiwan",
    ),
)


def get_or_create_demo_buffett_portfolio(session: Session) -> Portfolio:
    """Create or update a Berkshire-inspired portfolio with Decimal allocations.

    The reference prices make the seeded position values add up to the intended
    28/11/16/9/5 allocation profile. Valuation and allocation services apply
    current cached market data when the portfolio is displayed.
    """
    positions = [
        Position(
            asset_name=position.name,
            ticker=position.ticker,
            isin=position.isin,
            currency="USD",
            quantity=position.target_value / position.unit_cost,
            unit_cost=position.unit_cost,
            acquisition_date=date.today(),
            portfolio_id=0,
        )
        for position in _DEMO_POSITIONS
    ]
    try:
        demo_user = _get_or_create_demo_user(session)
        if demo_user.id is None:
            raise PersistenceError
        existing = portfolio_crud.get_portfolio_by_name_for_user(
            session, demo_user.id, DEMO_PORTFOLIO_NAME
        )
        if existing is not None:
            existing.broker = DEMO_BROKER
            existing.description = "Berkshire Hathaway-inspired equity allocation demo."
            return portfolio_crud.replace_positions(session, existing, positions)
        portfolio = Portfolio(
            name=DEMO_PORTFOLIO_NAME,
            broker=DEMO_BROKER,
            description="Berkshire Hathaway-inspired equity allocation demo.",
            user_id=demo_user.id,
        )
        return portfolio_crud.create_portfolio_with_positions(
            session, portfolio, positions
        )
    except SQLAlchemyError as error:
        session.rollback()
        raise PersistenceError from error


def get_demo_buffett_portfolio(session: Session) -> Portfolio | None:
    """Return the seeded public demo portfolio without exposing its owner."""
    return portfolio_crud.get_demo_portfolio(session, DEMO_PORTFOLIO_NAME)


def get_demo_ai_analysis() -> AIAnalysisResponse:
    """Return the dedicated report for the public read-only demo."""
    from portfolio_assistant.core.utils import get_now_utc

    return AIAnalysisResponse(
        analysis_text=DEMO_AI_ANALYSIS,
        persona_id="WARREN_BUFFETT",
        user_context=None,
        cached=True,
        created_at=get_now_utc(),
    )


def _get_or_create_demo_user(session: Session) -> User:
    """Return the non-login system account that owns public demo data."""
    user = user_crud.get_demo_user(session)
    if user is not None:
        return user
    settings = get_settings()
    user = user_crud.get_user_by_email(session, settings.demo_user_email)
    if user is not None:
        user.is_demo = True
        user.is_active = False
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
    user = User(
        email=settings.demo_user_email,
        full_name="System Demo User",
        hashed_password="system-demo-account",
        is_active=False,
        is_demo=True,
    )
    return user_crud.create_user(session, user)


def get_demo_portfolio_allocations() -> PortfolioAllocationResponse:
    """Return public demo allocations using the same reference position data."""
    total_value = sum(
        (position.target_value for position in _DEMO_POSITIONS),
        start=Decimal("0"),
    )
    allocations = [
        AssetAllocation(
            ticker=position.ticker,
            quantity=position.target_value / position.unit_cost,
            current_price=position.unit_cost,
            market_value=position.target_value,
            percentage=(position.target_value / total_value) * Decimal("100"),
            sector=position.sector,
            region=position.region,
        )
        for position in _DEMO_POSITIONS
    ]
    return PortfolioAllocationResponse(
        portfolio_id=None,
        total_value=total_value,
        allocations=allocations,
    )


def get_demo_asset_names() -> dict[str, str]:
    """Return the display name associated with each public demo ticker."""
    return {position.ticker: position.name for position in _DEMO_POSITIONS}
