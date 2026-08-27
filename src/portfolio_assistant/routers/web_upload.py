"""Portfolio upload endpoint."""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from portfolio_assistant.core.database import get_db_session
from portfolio_assistant.core.exceptions import (
    InvalidImportTypeError,
    PersistenceError,
    PortfolioImportError,
    PortfolioNotFoundError,
)
from portfolio_assistant.crud.portfolio import get_portfolios_for_user
from portfolio_assistant.dependencies import get_current_user, get_persisted_user_id
from portfolio_assistant.models.portfolio import Currency
from portfolio_assistant.models.user import User
from portfolio_assistant.routers.web_dashboard import _valuation_context
from portfolio_assistant.services.ai.gemini import GeminiAIService
from portfolio_assistant.services.parser.degiro import DegiroPortfolioParser
from portfolio_assistant.services.parser.fio_broker import FioBrokerPortfolioParser
from portfolio_assistant.services.portfolio_service import PortfolioService
from portfolio_assistant.services.valuation.engine import ValuationService

from .web import (
    get_fio_parser,
    get_gemini_service,
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
    gemini_service: Annotated[GeminiAIService, Depends(get_gemini_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service)],
    portfolio_id: Annotated[str, Form()],
    import_type: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
) -> HTMLResponse:
    """Import one broker file, persist it, and render its analysis."""
    logger.info(
        "Upload request received: portfolio=%s, type=%s, file=%s",
        portfolio_id,
        import_type,
        file.filename,
    )
    if portfolio_id == "all":
        logger.warning("Upload rejected: Aggregated portfolio")
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot upload data to aggregated view. Please select a specific "
                "portfolio."
            ),
        )
    try:
        portfolio_id_int = int(portfolio_id)
    except ValueError:
        logger.error("Upload rejected: Invalid portfolio ID %s", portfolio_id)
        raise HTTPException(status_code=400, detail="Invalid portfolio ID.") from None

    user_id = get_persisted_user_id(current_user)
    portfolios = get_portfolios_for_user(session, user_id)
    try:
        imported = await portfolio_service.import_portfolio_file(
            session,
            user_id,
            portfolio_id_int,
            import_type,
            await file.read(),
            degiro_parser,
            fio_parser,
        )
        valued = await valuation_service.value_portfolio_async(
            imported, target_currency=Currency.CZK
        )
        context = _success_context(current_user, portfolios, portfolio_id_int, valued)
        context["ai_analysis_markdown"] = await gemini_service.analyze_portfolio(
            valued.to_anonymized()
        )
        return templates.TemplateResponse(request, "dashboard.html", context)

    except PortfolioNotFoundError:
        raise HTTPException(status_code=404, detail="Portfolio not found.") from None
    except InvalidImportTypeError:
        raise HTTPException(
            status_code=400, detail="Unsupported import type."
        ) from None
    except PersistenceError:
        raise HTTPException(
            status_code=500, detail="Database persistence failed."
        ) from None
    except PortfolioImportError as error:
        logger.info("Portfolio import rejected: %s", error)
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            _error_context(current_user, portfolios, int(portfolio_id), str(error)),
        )


def _success_context(
    user: User, portfolios: Any, portfolio_id: int, valued: Any
) -> dict[str, Any]:
    context = {
        "current_user": user,
        "current_user_email": user.email,
        "username": user.email,
        "ai_analysis_markdown": "",
        "portfolios": portfolios,
        "selected_portfolio_id": portfolio_id,
        "error": None,
    }
    context.update(_valuation_context(valued))
    return context


def _error_context(
    user: User, portfolios: Any, portfolio_id: int | str, error: str
) -> dict[str, Any]:
    return {
        "valued_portfolio": None,
        "total_value_formatted": None,
        "chart_data_json": None,
        "error": f"Error processing portfolio: {error}",
        "current_user": user,
        "current_user_email": user.email,
        "username": user.email,
        "ai_analysis_markdown": "",
        "portfolios": portfolios,
        "selected_portfolio_id": portfolio_id,
    }
