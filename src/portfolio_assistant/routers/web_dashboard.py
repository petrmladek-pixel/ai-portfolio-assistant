# app/routers/dashboard.py
# Strict Python 3.12, under 150 lines of code. No Czech diacritics.
import json
import logging
from collections.abc import Sequence
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from portfolio_assistant.core.exceptions import PersistenceError
from portfolio_assistant.crud.portfolio import (
    get_portfolio_for_user,
    get_portfolios_for_user,
)
from portfolio_assistant.dependencies import (
    get_optional_current_user,
    get_persisted_user_id,
)
from portfolio_assistant.models.db_models import Portfolio
from portfolio_assistant.models.portfolio import (
    Currency,
    ImportedPortfolio,
    StockPosition,
)
from portfolio_assistant.models.user import User
from portfolio_assistant.models.valuation import ValuedPortfolio
from portfolio_assistant.services.ai.gemini import GeminiAIService
from portfolio_assistant.services.portfolio_aggregation_service import (
    PortfolioAggregationService,
)
from portfolio_assistant.services.portfolio_merger import PortfolioMerger
from portfolio_assistant.services.portfolio_service import PortfolioService
from portfolio_assistant.services.valuation.engine import ValuationService

from ..core.database import get_db_session
from .web import (
    format_currency,
    get_gemini_service,
    get_portfolio_aggregation_service,
    get_portfolio_merger,
    get_portfolio_service,
    get_valuation_service,
    templates,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# Define safe fallback context to prevent Jinja2 rendering crashes on empty data
EMPTY_DASHBOARD_CONTEXT: dict[str, Any] = {
    "valued_portfolio": None,
    "total_value_formatted": "0,00",
    "positions_count": "0",
    "sector_count": "0",
    "region_count": "0",
    "daily_change_pct": "0,0 %",
    "month_change_pct": "0,0",
    "positions": [],
    "top_weights": [],
    "chart_data_json": json.dumps({"labels": [], "weights": []}),
    "sector_allocation_json": json.dumps([]),
    "geo_allocation_json": json.dumps([]),
    "ai_analysis_markdown": "Zatim zadna data k analyze.",
}


@router.get("/", response_class=HTMLResponse)
async def dashboard_get(
    request: Request,
    valuation_service: Annotated[ValuationService, Depends(get_valuation_service)],
    gemini_service: Annotated[GeminiAIService, Depends(get_gemini_service)],
    portfolio_merger: Annotated[PortfolioMerger, Depends(get_portfolio_merger)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service)],
    portfolio_aggregation: Annotated[
        PortfolioAggregationService, Depends(get_portfolio_aggregation_service)
    ],
    session: Annotated[Session, Depends(get_db_session)],
    portfolio_id: str | int | None = None,
    current_user: Annotated[User | None, Depends(get_optional_current_user)] = None,
) -> HTMLResponse:
    """Render the dashboard and optional saved portfolio analysis."""
    if current_user is None:
        return templates.TemplateResponse(
            request, "dashboard.html", _get_guest_context()
        )

    # 1. Clean input normalization (Look Before You Leap)
    # Convert and normalize portfolio_id strictly to: int | Literal["all"] | None
    norm_id: int | str | None = None
    if isinstance(portfolio_id, str):
        val_lower = portfolio_id.lower()
        if val_lower == "all":
            norm_id = "all"
        elif val_lower.isdigit():
            norm_id = int(val_lower)
    elif isinstance(portfolio_id, int):
        norm_id = portfolio_id

    # 2. Initialize context with safe empty defaults immediately
    context = _base_context(current_user, norm_id)
    context.update(EMPTY_DASHBOARD_CONTEXT)

    user_id = get_persisted_user_id(current_user)

    try:
        portfolio_service.ensure_default_portfolio(session, user_id)
        portfolios = get_portfolios_for_user(session, user_id)
        context["portfolios"] = portfolios
        context["has_data"] = True

        # 3. Determine selected portfolio ID with simple, type-safe logic
        selected_id: int | str | None = None
        if norm_id == "all":
            selected_id = "all"
        elif isinstance(norm_id, int) and any(p.id == norm_id for p in portfolios):
            selected_id = norm_id
        else:
            selected_id = portfolios[0].id if portfolios else None

        context["selected_portfolio_id"] = selected_id

        # 4. Fetch, merge, and value positions
        selected = _select_portfolios(session, user_id, norm_id, portfolios)
        imported = _to_imported_portfolios(selected)

        if imported:
            merged = _merge_portfolios(imported, portfolio_merger)
            valued = await valuation_service.value_portfolio_async(
                merged, target_currency=Currency.CZK, db_session=session
            )
            context.update(_valuation_context(valued))

            # Get portfolio allocation data for sector and country charts
            # Use the first portfolio's ID for allocation (or merged portfolio)
            if selected and selected[0].id is not None:
                allocation = portfolio_aggregation.get_portfolio_allocation(
                    selected[0].id
                )
                context.update(_allocation_context(allocation))

            # NOTE FOR PRODUCTION: Awaiting LLM API on page load is slow.
            # In next milestone, load this asynchronously via an API route.
            context["ai_analysis_markdown"] = await gemini_service.analyze_portfolio(
                valued.to_anonymized()
            )

    except (PersistenceError, SQLAlchemyError):
        logger.exception("Database error while loading dashboard")
        context["error"] = "Database persistence failed."
    except Exception:
        logger.exception("Unexpected error while loading dashboard")
        context["error"] = "An unexpected error occurred."

    return templates.TemplateResponse(request, "dashboard.html", context)


def _base_context(user: User | None, portfolio_id: str | int | None) -> dict[str, Any]:
    return {
        "current_user": user,
        "current_user_email": user.email if user else None,
        "valued_portfolio": None,
        "total_value_formatted": "0,00",
        "positions_count": "0",
        "sector_count": "0",
        "region_count": "0",
        "daily_change_pct": "0,0 %",
        "month_change_pct": "0,0",
        "positions": [],
        "top_weights": [],
        "chart_data_json": json.dumps({"labels": [], "weights": []}),
        "sector_allocation_json": json.dumps([]),
        "geo_allocation_json": json.dumps([]),
        "has_data": False,
        "error": None,
        "username": user.email if user else None,
        "ai_analysis_markdown": "Nahrajte CSV data pro analyzu.",
        "portfolios": [],
        "selected_portfolio_id": portfolio_id,
    }


def _get_guest_context() -> dict[str, Any]:
    return {
        "current_user": None,
        "current_user_email": "Demo Ucet",
        "username": None,
        "total_value_formatted": "10 000 000,00",
        "month_change_pct": "3.8",
        "positions_count": "5+",
        "sector_count": "5",
        "region_count": "1",
        "daily_change_pct": "+1.1 %",
        "has_data": True,
        "positions": [
            {
                "ticker": "AAPL",
                "name": "Apple Inc.",
                "value_formatted": "4 000 000,00",
                "weight": 40,
            },
            {
                "ticker": "AXP",
                "name": "American Express",
                "value_formatted": "1 200 000,00",
                "weight": 12,
            },
            {
                "ticker": "BAC",
                "name": "Bank of America",
                "value_formatted": "1 000 000,00",
                "weight": 10,
            },
            {
                "ticker": "KO",
                "name": "The Coca-Cola Co.",
                "value_formatted": "800 000,00",
                "weight": 8,
            },
            {
                "ticker": "OXY",
                "name": "Occidental Petroleum",
                "value_formatted": "600 000,00",
                "weight": 6,
            },
        ],
        "top_weights": [
            {"label": "Apple Inc.", "value": 40, "color": "#0f172a"},
            {"label": "American Express", "value": 12, "color": "#0d9488"},
            {"label": "Bank of America", "value": 10, "color": "#3b82f6"},
            {"label": "The Coca-Cola Co.", "value": 8, "color": "#d97706"},
            {"label": "Occidental Petroleum", "value": 6, "color": "#6366f1"},
        ],
        "chart_data_json": json.dumps(
            {
                "labels": [
                    "Apple Inc.",
                    "American Express",
                    "Bank of America",
                    "The Coca-Cola Co.",
                    "Occidental Petroleum",
                ],
                "weights": [40, 12, 10, 8, 6],
            }
        ),
        "sector_allocation_json": json.dumps(
            [
                {"label": "IT", "value": 40},
                {"label": "Finance", "value": 22},
                {"label": "Spotrebni", "value": 8},
                {"label": "Energetika", "value": 6},
                {"label": "Ostatni", "value": 24},
            ]
        ),
        "geo_allocation_json": json.dumps(
            [{"label": "USA", "value": 90}, {"label": "Ostatni", "value": 10}]
        ),
        "ai_analysis_markdown": "Demo portfolio Berkshire Hathaway analysis.",
        "portfolios": [],
        "selected_portfolio_id": None,
        "error": None,
    }


def _select_portfolios(
    session: Session,
    user_id: int,
    portfolio_id: str | int | None,
    portfolios: Sequence[Portfolio],
) -> list[Portfolio]:
    if portfolio_id is None:
        return list(portfolios)
    if str(portfolio_id).lower() == "all":
        return list(portfolios)
    try:
        pid = int(portfolio_id)
    except (TypeError, ValueError):
        return list(portfolios)
    p = get_portfolio_for_user(session, pid, user_id)
    return [p] if p is not None else []


def _to_imported_portfolios(portfolios: Sequence[Portfolio]) -> list[ImportedPortfolio]:
    imported: list[ImportedPortfolio] = []
    for p in portfolios:
        if p.positions:
            imported.append(
                ImportedPortfolio(
                    broker_name=p.name,
                    imported_at=datetime.now(),
                    positions=[
                        StockPosition(
                            ticker=pos.ticker,
                            name=pos.asset_name,
                            quantity=pos.quantity,
                            average_price=pos.unit_cost,
                            currency=Currency(pos.currency),
                        )
                        for pos in p.positions
                    ],
                )
            )
    return imported


def _merge_portfolios(
    portfolios: list[ImportedPortfolio], merger: PortfolioMerger
) -> ImportedPortfolio:
    return (
        portfolios[0] if len(portfolios) == 1 else merger.merge_portfolios(portfolios)
    )


def _valuation_context(valued: ValuedPortfolio) -> dict[str, Any]:
    # Muted Corporate Slate palette for maximum contrast and legibility
    colors = [
        "#0f172a",
        "#0d9488",
        "#3b82f6",
        "#d97706",
        "#6366f1",
        "#16a34a",
        "#be123c",
        "#475569",
        "#cbd5e1",
    ]
    formatted_positions = [
        {
            "ticker": pos.ticker,
            "name": pos.name or pos.ticker,
            "value_formatted": format_currency(pos.total_value_target),
            "weight": round(float(pos.weight * 100), 1),
        }
        for pos in valued.positions
    ]
    top_weights = [
        {
            "label": pos.name or pos.ticker,
            "value": round(float(pos.weight * 100), 1),
            "color": colors[i % len(colors)],
        }
        for i, pos in enumerate(valued.positions[:5])
    ]
    return {
        "valued_portfolio": valued,
        "total_value_formatted": format_currency(valued.total_value),
        "positions_count": str(len(valued.positions)),
        "positions": formatted_positions,
        "top_weights": top_weights,
        "has_data": True,
        "chart_data_json": json.dumps(
            {
                "labels": [p.ticker for p in valued.positions],
                "weights": [float(p.weight * 100) for p in valued.positions],
            }
        ),
        # Temporary mock for Milestone 2, before Milestone 6
        # including real yfinance sectors/countries
        "sector_allocation_json": json.dumps([{"label": "Akcie", "value": 100}]),
        "geo_allocation_json": json.dumps([{"label": "Globalni", "value": 100}]),
    }


def _allocation_context(allocation: dict[str, Any]) -> dict[str, Any]:
    """Convert allocation data to context for Chart.js donut charts.

    Args:
        allocation: Dictionary with sectors and countries allocation data.

    Returns:
        dict[str, Any]: Context with JSON strings for sector and geo allocation.
    """
    # Convert sectors data to list format for Chart.js
    sectors_list = [
        {"label": label, "value": value}
        for label, value in zip(
            allocation["sectors"]["labels"],
            allocation["sectors"]["data"],
            strict=True,
        )
    ]

    # Convert countries data to list format for Chart.js
    countries_list = [
        {"label": label, "value": value}
        for label, value in zip(
            allocation["countries"]["labels"],
            allocation["countries"]["data"],
            strict=True,
        )
    ]

    return {
        "sector_allocation_json": json.dumps(sectors_list),
        "geo_allocation_json": json.dumps(countries_list),
        "sector_count": str(len(allocation["sectors"]["labels"])),
        "region_count": str(len(allocation["countries"]["labels"])),
    }
