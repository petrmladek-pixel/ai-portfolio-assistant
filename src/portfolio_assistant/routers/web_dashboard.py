"""Dashboard rendering endpoint."""

import json
import logging
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from portfolio_assistant.crud.portfolio import (
    get_portfolio_for_user,
    get_portfolios_for_user,
)
from portfolio_assistant.dependencies import (
    get_optional_current_user,
    get_persisted_user_id,
)
from portfolio_assistant.models.portfolio import (
    Currency,
    ImportedPortfolio,
    StockPosition,
)
from portfolio_assistant.models.user import User
from portfolio_assistant.services.ai.gemini import GeminiAIService
from portfolio_assistant.services.portfolio_merger import PortfolioMerger
from portfolio_assistant.services.valuation.engine import ValuationService

from ..core.database import get_db_session
from .web import (
    format_currency,
    get_gemini_service,
    get_portfolio_merger,
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
    session: Annotated[Session, Depends(get_db_session)],
    portfolio_id: int | None = None,
    current_user: Annotated[User | None, Depends(get_optional_current_user)] = None,
) -> HTMLResponse:
    """Render the dashboard and optional saved portfolio analysis."""
    context: dict[str, Any] = _base_context(current_user, portfolio_id)
    if current_user is not None:
        user_id = get_persisted_user_id(current_user)
        try:
            portfolios = get_portfolios_for_user(session, user_id)
            context["portfolios"] = portfolios
            selected = _select_portfolios(session, user_id, portfolio_id, portfolios)
            imported = _to_imported_portfolios(selected)
            if imported:
                merged = _merge_portfolios(imported, portfolio_merger)
                valued = await valuation_service.value_portfolio_async(
                    merged, target_currency=Currency.CZK
                )
                context.update(_valuation_context(valued))
                context[
                    "ai_analysis_markdown"
                ] = await gemini_service.analyze_portfolio(valued.to_anonymized())
        except SQLAlchemyError:
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
    session: Session, user_id: int, portfolio_id: int | None, portfolios: Any
) -> list[Any]:
    if portfolio_id is None:
        return list(portfolios)
    portfolio = get_portfolio_for_user(session, portfolio_id, user_id)
    return [portfolio] if portfolio is not None else []


def _to_imported_portfolios(portfolios: list[Any]) -> list[ImportedPortfolio]:
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


def _valuation_context(valued: Any) -> dict[str, Any]:
    return {
        "valued_portfolio": valued,
        "total_value_formatted": format_currency(valued.total_value),
        "chart_data_json": json.dumps(
            {
                "labels": [position.ticker for position in valued.positions],
                "weights": [
                    float(position.weight * 100) for position in valued.positions
                ],
            }
        ),
    }
