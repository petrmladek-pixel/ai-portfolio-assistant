"""HTTP endpoints for AI portfolio analysis, chat, and prompt preferences."""

import logging
from datetime import timedelta
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
    PortfolioAnalysisResponse,
    PromptResponse,
    PromptUpdateRequest,
)
from portfolio_assistant.models.user import User
from portfolio_assistant.services.ai_analysis import (
    AIAnalysisService,
    AnalysisCooldownError,
)
from portfolio_assistant.services.ai_analysis_service import (
    AIAnalysisService as PersonaAIAnalysisService,
)
from portfolio_assistant.services.ai_chat_service import AIChatService
from portfolio_assistant.services.user_service import UserService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["ai"])


def get_analysis_service() -> AIAnalysisService:
    """Provide the portfolio analysis workflow service."""
    return AIAnalysisService()


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
    "/portfolios/{portfolio_id}/analysis/latest",
    response_model=PortfolioAnalysisResponse | None,
)
def get_latest_analysis(
    portfolio_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    analysis_service: Annotated[AIAnalysisService, Depends(get_analysis_service)],
) -> PortfolioAnalysisResponse | None:
    """Return the latest cached analysis for the authenticated user's portfolio."""
    try:
        analysis = analysis_service.get_latest_analysis(
            session,
            portfolio_id,
            current_user,
        )
        if analysis is None:
            return None
        return PortfolioAnalysisResponse.model_validate(analysis)
    except PortfolioNotFoundError:
        raise _portfolio_not_found() from None
    except SQLAlchemyError:
        logger.exception("Database error while retrieving portfolio analysis")
        raise _persistence_error() from None


@router.post(
    "/portfolios/{portfolio_id}/analyze",
    response_model=PortfolioAnalysisResponse,
)
async def analyze_portfolio(
    portfolio_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    analysis_service: Annotated[AIAnalysisService, Depends(get_analysis_service)],
) -> PortfolioAnalysisResponse:
    """Generate and cache an AI analysis for the authenticated user's portfolio."""
    try:
        analysis = await analysis_service.analyze_portfolio(
            session,
            portfolio_id,
            current_user,
        )
        return PortfolioAnalysisResponse.model_validate(analysis)
    except AnalysisCooldownError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_cooldown_message(error.remaining_time),
        ) from None
    except PortfolioNotFoundError:
        raise _portfolio_not_found() from None
    except PersistenceError:
        logger.exception("Database error while saving portfolio analysis")
        raise _persistence_error() from None
    except AIAnalysisError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from None


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
) -> AIAnalysisResponse:
    """Return a matching cached report or generate a persona-aware report."""
    if current_user.id is None:
        raise _portfolio_not_found()
    portfolio = portfolio_crud.get_portfolio_for_user(
        session,
        portfolio_id,
        current_user.id,
    )
    if portfolio is None:
        raise _portfolio_not_found()
    try:
        return await analysis_service.get_or_generate_analysis(
            session,
            portfolio_id,
            payload,
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


def _portfolio_not_found() -> HTTPException:
    """Build the common missing-portfolio HTTP response."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Portfolio not found.",
    )


def _persistence_error() -> HTTPException:
    """Build the common database-failure HTTP response."""
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Database persistence failed.",
    )


def _cooldown_message(remaining_time: timedelta) -> str:
    """Describe the seven-day analysis cooldown and its remaining duration."""
    total_seconds = max(0, int(remaining_time.total_seconds()))
    days, remainder = divmod(total_seconds, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes = remainder // 60
    parts = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes or not parts:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    return (
        "Analysis is limited to one request every 7 days. Remaining time: "
        + ", ".join(parts)
        + "."
    )
