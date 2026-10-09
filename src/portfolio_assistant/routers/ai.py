"""HTTP endpoints for AI portfolio analysis, chat, and prompt preferences."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from portfolio_assistant.core.database import get_db_session
from portfolio_assistant.core.exceptions import (
    AIAnalysisError,
    PersistenceError,
    PortfolioNotFoundError,
)
from portfolio_assistant.crud import portfolio as portfolio_crud
from portfolio_assistant.dependencies import get_current_user
from portfolio_assistant.models.ai import (
    AIAnalysisRequest,
    AIAnalysisResponse,
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    InvestorContextResponse,
    InvestorContextUpdateRequest,
    PromptResponse,
    PromptUpdateRequest,
)
from portfolio_assistant.models.user import User
from portfolio_assistant.services.ai_analysis_service import (
    AIAnalysisService as PersonaAIAnalysisService,
)
from portfolio_assistant.services.ai_chat_service import AIChatService
from portfolio_assistant.services.demo_service import (
    get_demo_ai_analysis,
    get_demo_buffett_portfolio,
)
from portfolio_assistant.services.user_service import UserService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["ai"])


def get_persona_analysis_service() -> PersonaAIAnalysisService:
    """Provide the persona-aware portfolio analysis workflow service."""
    return PersonaAIAnalysisService()


def get_chat_service() -> AIChatService:
    """Provide the portfolio chat workflow service."""
    return AIChatService()


def get_user_service() -> UserService:
    """Provide the user preference workflow service."""
    return UserService()


@router.get(
    "/portfolios/demo/ai-analysis",
    response_model=AIAnalysisResponse,
)
def get_public_demo_ai_analysis() -> AIAnalysisResponse:
    """Return the fixed, read-only report for the public demo portfolio."""
    return get_demo_ai_analysis()


@router.post(
    "/portfolios/{portfolio_id}/ai-analysis",
    response_model=AIAnalysisResponse,
)
async def get_or_generate_ai_analysis(
    portfolio_id: int,
    payload: AIAnalysisRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    analysis_service: Annotated[
        PersonaAIAnalysisService,
        Depends(get_persona_analysis_service),
    ],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> AIAnalysisResponse:
    """Return a matching cached report or generate a persona-aware report."""
    if current_user.id is None:
        raise _portfolio_not_found()
    if _is_demo_portfolio(session, portfolio_id):
        return get_demo_ai_analysis()
    portfolio = portfolio_crud.get_portfolio_for_user(
        session,
        portfolio_id,
        current_user.id,
    )
    if portfolio is None:
        raise _portfolio_not_found()
    try:
        user = _update_context_from_analysis_request(
            session,
            current_user,
            payload,
            user_service,
        )
        request = payload.model_copy(update={"user_context": user.investor_context})
        return await analysis_service.get_or_generate_analysis(
            session,
            portfolio_id,
            request,
            current_user.id,
        )
    except AIAnalysisError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from None
    except SQLAlchemyError:
        logger.exception("Database error while handling persona-aware analysis")
        raise _persistence_error() from None


@router.get(
    "/portfolios/{portfolio_id}/ai-analysis",
    response_model=AIAnalysisResponse | None,
)
async def get_latest_persona_ai_analysis(
    portfolio_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    analysis_service: Annotated[
        PersonaAIAnalysisService,
        Depends(get_persona_analysis_service),
    ],
) -> AIAnalysisResponse | None:
    """Return the newest valid persona-aware cache entry for a portfolio."""
    if current_user.id is None:
        raise _portfolio_not_found()
    if _is_demo_portfolio(session, portfolio_id):
        return get_demo_ai_analysis()
    portfolio = portfolio_crud.get_portfolio_for_user(
        session,
        portfolio_id,
        current_user.id,
    )
    if portfolio is None:
        raise _portfolio_not_found()
    try:
        return await analysis_service.get_latest_cached_analysis(
            session,
            current_user.id,
            current_user.investor_context,
        )
    except SQLAlchemyError:
        logger.exception("Database error while retrieving persona-aware analysis")
        raise _persistence_error() from None


@router.post(
    "/portfolios/ai-analysis/all",
    response_model=AIAnalysisResponse,
)
async def generate_all_portfolios_ai_analysis(
    payload: AIAnalysisRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    analysis_service: Annotated[
        PersonaAIAnalysisService,
        Depends(get_persona_analysis_service),
    ],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> AIAnalysisResponse:
    """Generate an uncached report from every portfolio owned by the user."""
    if current_user.id is None:
        raise _portfolio_not_found()
    try:
        user = _update_context_from_analysis_request(
            session,
            current_user,
            payload,
            user_service,
        )
        request = payload.model_copy(update={"user_context": user.investor_context})
        return await analysis_service.generate_all_portfolios_analysis(
            session,
            current_user.id,
            request,
        )
    except AIAnalysisError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from None


@router.get(
    "/portfolios/ai-analysis/all",
    response_model=AIAnalysisResponse | None,
)
async def get_latest_all_portfolios_ai_analysis(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    analysis_service: Annotated[
        PersonaAIAnalysisService,
        Depends(get_persona_analysis_service),
    ],
) -> AIAnalysisResponse | None:
    """Return the persisted wealth report for the all-portfolios dashboard."""
    if current_user.id is None:
        raise _portfolio_not_found()
    try:
        return await analysis_service.get_latest_all_portfolios_analysis(
            session,
            current_user.id,
            current_user.investor_context,
        )
    except SQLAlchemyError:
        logger.exception("Database error while retrieving wealth analysis")
        raise _persistence_error() from None


@router.get(
    "/portfolios/{portfolio_id}/chat/history",
    response_model=list[ChatMessageResponse],
)
def get_chat_history(
    portfolio_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    chat_service: Annotated[AIChatService, Depends(get_chat_service)],
) -> list[ChatMessageResponse]:
    """Return the ten newest chat messages for the authenticated user's portfolio."""
    try:
        history = chat_service.get_chat_history(session, portfolio_id, current_user)
        return [ChatMessageResponse.model_validate(message) for message in history]
    except PortfolioNotFoundError:
        raise _portfolio_not_found() from None
    except SQLAlchemyError:
        logger.exception("Database error while retrieving portfolio chat history")
        raise _persistence_error() from None


@router.post(
    "/portfolios/{portfolio_id}/chat",
    response_model=ChatResponse,
)
async def chat_with_portfolio(
    portfolio_id: int,
    payload: ChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    chat_service: Annotated[AIChatService, Depends(get_chat_service)],
) -> ChatResponse:
    """Generate an assistant response using the authenticated user's portfolio."""
    try:
        response = await chat_service.handle_chat(
            session,
            portfolio_id,
            current_user,
            payload.message,
        )
        return ChatResponse(message=response)
    except PortfolioNotFoundError:
        raise _portfolio_not_found() from None
    except PersistenceError:
        logger.exception("Database error while saving portfolio chat")
        raise _persistence_error() from None
    except AIAnalysisError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from None


@router.get("/settings/prompt", response_model=PromptResponse)
def get_prompt(
    current_user: Annotated[User, Depends(get_current_user)],
) -> PromptResponse:
    """Return the authenticated user's custom AI system prompt."""
    return PromptResponse(prompt=current_user.analysis_prompt)


@router.post("/settings/prompt", response_model=PromptResponse)
def update_prompt(
    payload: PromptUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> PromptResponse:
    """Update the authenticated user's custom AI system prompt."""
    try:
        user = user_service.set_analysis_prompt(session, current_user, payload.prompt)
        return PromptResponse(prompt=user.analysis_prompt)
    except SQLAlchemyError:
        logger.exception("Database error while updating AI system prompt")
        raise _persistence_error() from None


@router.get("/settings/investor-context", response_model=InvestorContextResponse)
def get_investor_context(
    current_user: Annotated[User, Depends(get_current_user)],
) -> InvestorContextResponse:
    """Return the saved investor context shared by all portfolio views."""
    return InvestorContextResponse(investor_context=current_user.investor_context)


@router.put("/settings/investor-context", response_model=InvestorContextResponse)
def update_investor_context(
    payload: InvestorContextUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> InvestorContextResponse:
    """Persist a changed investor context independently of report generation."""
    try:
        user = user_service.set_investor_context(
            session,
            current_user,
            payload.investor_context,
        )
        return InvestorContextResponse(investor_context=user.investor_context)
    except SQLAlchemyError:
        logger.exception("Database error while updating investor context")
        raise _persistence_error() from None


def _portfolio_not_found() -> HTTPException:
    """Build the common missing-portfolio HTTP response."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Portfolio not found.",
    )


def _update_context_from_analysis_request(
    session: Session,
    user: User,
    payload: AIAnalysisRequest,
    user_service: UserService,
) -> User:
    """Persist an explicitly supplied context before generating a report."""
    if payload.user_context is None:
        return user
    return user_service.set_investor_context(session, user, payload.user_context)


def _is_demo_portfolio(session: Session, portfolio_id: int) -> bool:
    """Return whether an ID refers to the shared public demo portfolio."""
    portfolio = get_demo_buffett_portfolio(session)
    return portfolio is not None and portfolio.id == portfolio_id


def _persistence_error() -> HTTPException:
    """Build the common database-failure HTTP response."""
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Database persistence failed.",
    )
