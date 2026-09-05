"""Portfolio allocation API endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from portfolio_assistant.core.database import get_db_session
from portfolio_assistant.crud import portfolio as portfolio_crud
from portfolio_assistant.crud import transaction as transaction_crud
from portfolio_assistant.dependencies import get_current_user, get_persisted_user_id
from portfolio_assistant.models.allocation import PortfolioAllocationResponse
from portfolio_assistant.models.user import User
from portfolio_assistant.services.allocation import AllocationService
from portfolio_assistant.services.price_cache import PriceCacheService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portfolios", tags=["portfolio"])


@router.get("/{portfolio_id}/allocations", response_model=PortfolioAllocationResponse)
def get_portfolio_allocations(
    portfolio_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> PortfolioAllocationResponse:
    """Return the current market-value allocation for an owned portfolio."""
    try:
        user_id = get_persisted_user_id(current_user)
        portfolio = portfolio_crud.get_portfolio_for_user(
            session, portfolio_id, user_id
        )
        if portfolio is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found.",
            )
        tickers = transaction_crud.get_portfolio_tickers(session, portfolio_id)
        prices = PriceCacheService.get_current_prices(session, tickers)
        return AllocationService().calculate_portfolio_allocations(
            session, portfolio_id, prices
        )
    except HTTPException:
        raise
    except SQLAlchemyError:
        logger.exception("Database error while calculating portfolio allocations")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database persistence failed.",
        ) from None
    except Exception:
        logger.exception("Unexpected error while calculating portfolio allocations")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to calculate portfolio allocations.",
        ) from None
