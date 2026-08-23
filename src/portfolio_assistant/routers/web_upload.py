"""Portfolio upload endpoint."""

import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from portfolio_assistant.core.exceptions import PersistenceError, PortfolioNotFoundError
from portfolio_assistant.crud.portfolio import get_portfolios_for_user
from portfolio_assistant.dependencies import get_current_user, get_persisted_user_id
from portfolio_assistant.models.portfolio import Currency, ImportedPortfolio
from portfolio_assistant.models.user import User
from portfolio_assistant.services.ai.gemini import GeminiAIService
from portfolio_assistant.services.parser.degiro import DegiroPortfolioParser
from portfolio_assistant.services.parser.fio_broker import FioBrokerPortfolioParser
from portfolio_assistant.services.portfolio_merger import PortfolioMerger
from portfolio_assistant.services.portfolio_service import PortfolioService
from portfolio_assistant.services.valuation.engine import ValuationService

from ..core.database import get_db_session
from .web import (
    format_currency,
    get_fio_parser,
    get_gemini_service,
    get_portfolio_merger,
    get_portfolio_parser,
    get_portfolio_service,
    get_valuation_service,
    templates,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload", response_class=HTMLResponse)
async def upload_portfolio(
    request: Request,
    valuation_service: Annotated[ValuationService, Depends(get_valuation_service)],
    degiro_parser: Annotated[DegiroPortfolioParser, Depends(get_portfolio_parser)],
    fio_parser: Annotated[FioBrokerPortfolioParser, Depends(get_fio_parser)],
    portfolio_merger: Annotated[PortfolioMerger, Depends(get_portfolio_merger)],
    gemini_service: Annotated[GeminiAIService, Depends(get_gemini_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service)],
    portfolio_id: Annotated[int, Form()],
    degiro_file: Annotated[UploadFile | None, Form()] = None,
    fio_file: Annotated[UploadFile | None, Form()] = None,
) -> HTMLResponse:
    """Parse, persist, value, and render an uploaded portfolio."""
    user_id = get_persisted_user_id(current_user)
    portfolios = get_portfolios_for_user(session, user_id)
    try:
        imported = await _parse_files(degiro_file, fio_file, degiro_parser, fio_parser)
        final = _merge_portfolios(imported, portfolio_merger)
        portfolio_service.replace_imported_positions(
            session, user_id, portfolio_id, final
        )
        valued = await valuation_service.value_portfolio_async(
            final, target_currency=Currency.CZK
        )
        context = _success_context(current_user, portfolios, portfolio_id, valued)
        context["ai_analysis_markdown"] = await gemini_service.analyze_portfolio(
            valued.to_anonymized()
        )
        return templates.TemplateResponse(request, "dashboard.html", context)
    except PortfolioNotFoundError:
        raise HTTPException(status_code=404, detail="Portfolio not found.") from None
    except PersistenceError:
        raise HTTPException(
            status_code=500, detail="Database persistence failed."
        ) from None
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Failed to process portfolio upload")
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            _error_context(current_user, portfolios, portfolio_id, str(error)),
        )


async def _parse_files(
    degiro_file: UploadFile | None,
    fio_file: UploadFile | None,
    degiro_parser: DegiroPortfolioParser,
    fio_parser: FioBrokerPortfolioParser,
) -> list[ImportedPortfolio]:
    if degiro_file is None and fio_file is None:
        raise HTTPException(
            status_code=400,
            detail="At least one portfolio file must be provided.",
        )
    portfolios: list[ImportedPortfolio] = []
    if degiro_file is not None:
        portfolios.append(await degiro_parser.parse(await degiro_file.read()))
    if fio_file is not None:
        portfolios.append(await fio_parser.parse(await fio_file.read()))
    return portfolios


def _merge_portfolios(
    portfolios: list[ImportedPortfolio], merger: PortfolioMerger
) -> ImportedPortfolio:
    return (
        portfolios[0] if len(portfolios) == 1 else merger.merge_portfolios(portfolios)
    )


def _success_context(
    user: User, portfolios: Any, portfolio_id: int, valued: Any
) -> dict[str, Any]:
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
        "error": None,
        "username": user.email,
        "ai_analysis_markdown": "",
        "portfolios": portfolios,
        "selected_portfolio_id": portfolio_id,
    }


def _error_context(
    user: User, portfolios: Any, portfolio_id: int, error: str
) -> dict[str, Any]:
    return {
        "valued_portfolio": None,
        "total_value_formatted": None,
        "chart_data_json": None,
        "error": f"Error processing portfolio: {error}",
        "username": user.email,
        "ai_analysis_markdown": "",
        "portfolios": portfolios,
        "selected_portfolio_id": portfolio_id,
    }
