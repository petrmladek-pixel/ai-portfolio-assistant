"""Dashboard rendering endpoint."""

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
from portfolio_assistant.services.portfolio_merger import PortfolioMerger
from portfolio_assistant.services.portfolio_service import PortfolioService
from portfolio_assistant.services.valuation.engine import ValuationService

from ..core.database import get_db_session
from .web import (
    format_currency,
    get_gemini_service,
    get_portfolio_merger,
    get_portfolio_service,
    get_valuation_service,
    templates,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard_get(
    request: Request,
    valuation_service: Annotated[ValuationService, Depends(get_valuation_service)],
    gemini_service: Annotated[GeminiAIService, Depends(get_gemini_service)],
    portfolio_merger: Annotated[PortfolioMerger, Depends(get_portfolio_merger)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service)],
    session: Annotated[Session, Depends(get_db_session)],
    portfolio_id: int | None = None,
    current_user: Annotated[User | None, Depends(get_optional_current_user)] = None,
) -> HTMLResponse:
    """Render the dashboard and optional saved portfolio analysis."""
    if current_user is None:
        context: dict[str, Any] = {
            "current_user": None,
            "current_user_email": None,
            "username": None,
            "total_value_formatted": "10 000 000,00",
            "month_change_pct": "3.8",
            "positions_count": "5+",
            "sector_count": "5",
            "region_count": "1",
            "daily_change_pct": "+1.1 %",
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
                {
                    "ticker": "CASH",
                    "name": "Hotovost a statni dluhopisy",
                    "value_formatted": "2 400 000,00",
                    "weight": 24,
                },
            ],
            "top_weights": [
                {"label": "AAPL", "value": 40, "color": "#475569"},
                {"label": "AXP", "value": 12, "color": "#6b7280"},
                {"label": "BAC", "value": 10, "color": "#0f766e"},
                {"label": "KO", "value": 8, "color": "#b45309"},
                {"label": "OXY", "value": 6, "color": "#374151"},
            ],
            "chart_data_json": json.dumps(
                {
                    "labels": ["AAPL", "AXP", "BAC", "KO", "OXY", "CASH"],
                    "weights": [40, 12, 10, 8, 6, 24],
                }
            ),
            "ai_analysis_markdown": (
                "Berkshire Hathaway demo portfolio analysis: "
                "highly concentrated in stable cash-generating "
                "giants with a strong cash reserve."
            ),
            "portfolios": [],
            "selected_portfolio_id": None,
            "error": None,
        }
        return templates.TemplateResponse(request, "dashboard.html", context)

    context = _base_context(current_user, portfolio_id)
    user_id = get_persisted_user_id(current_user)
    try:
        portfolio_service.ensure_default_portfolio(session, user_id)
        portfolios = get_portfolios_for_user(session, user_id)
        if portfolio_id is None and portfolios:
            context["selected_portfolio_id"] = portfolios[0].id
        context["portfolios"] = portfolios
        selected = _select_portfolios(session, user_id, portfolio_id, portfolios)
        imported = _to_imported_portfolios(selected)
        if imported:
            merged = _merge_portfolios(imported, portfolio_merger)
            valued = await valuation_service.value_portfolio_async(
                merged, target_currency=Currency.CZK
            )
            context.update(_valuation_context(valued))
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


def _base_context(user: User | None, portfolio_id: int | None) -> dict[str, Any]:
    return {
        "valued_portfolio": None,
        "total_value_formatted": None,
        "chart_data_json": None,
        "error": None,
        "username": user.email if user else None,
        "ai_analysis_markdown": "",
        "portfolios": [],
        "selected_portfolio_id": portfolio_id,
    }


def _select_portfolios(
    session: Session,
    user_id: int,
    portfolio_id: int | None,
    portfolios: Sequence[Portfolio],
) -> list[Portfolio]:
    if portfolio_id is None:
        return list(portfolios)
    portfolio = get_portfolio_for_user(session, portfolio_id, user_id)
    return [portfolio] if portfolio is not None else []


def _to_imported_portfolios(portfolios: Sequence[Portfolio]) -> list[ImportedPortfolio]:
    imported: list[ImportedPortfolio] = []
    for portfolio in portfolios:
        if portfolio.positions:
            imported.append(
                ImportedPortfolio(
                    broker_name=portfolio.name,
                    imported_at=datetime.now(),
                    positions=[
                        StockPosition(
                            ticker=position.ticker,
                            name=position.asset_name,
                            quantity=position.quantity,
                            average_price=position.unit_cost,
                            currency=Currency(position.currency),
                        )
                        for position in portfolio.positions
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
    colors = ["#475569", "#6b7280", "#0f766e", "#b45309", "#374151"]
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
            "label": pos.ticker,
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
        "chart_data_json": json.dumps(
            {
                "labels": [position.ticker for position in valued.positions],
                "weights": [
                    float(position.weight * 100) for position in valued.positions
                ],
            }
        ),
    }
