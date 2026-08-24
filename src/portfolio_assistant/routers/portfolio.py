"""Portfolio persistence and retrieval router."""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from portfolio_assistant.models.portfolio import PortfolioCreate

from ..core.database import get_db_session
from ..core.exceptions import PersistenceError
from ..crud import portfolio as portfolio_crud
from ..dependencies import get_current_user, get_persisted_user_id
from ..models.db_models import Portfolio
from ..models.user import User
from ..services.portfolio_service import PortfolioService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


def get_portfolio_service() -> PortfolioService:
    """Provide the portfolio persistence service."""
    return PortfolioService()


@router.post("", response_model=Portfolio, status_code=status.HTTP_201_CREATED)
async def create_portfolio(
    portfolio_data: PortfolioCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service)],
) -> Portfolio:
    """Create a new portfolio for the logged-in user."""
    user_id = get_persisted_user_id(current_user)
    try:
        return portfolio_service.create(
            session, portfolio_data.name, portfolio_data.broker, user_id
        )
    except PersistenceError:
        logger.exception("Database error while creating portfolio")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database persistence failed.",
        ) from None


@router.get("/me")
async def get_my_portfolio(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """
    Fetch the saved positions from the database for the logged-in user.
    """
    user_id = get_persisted_user_id(current_user)
    try:
        portfolio = portfolio_crud.get_first_portfolio_for_user(session, user_id)

        if not portfolio:
            return {
                "broker_name": "None",
                "positions": [],
            }

        # Build position representation
        positions_data = []
        for pos in portfolio.positions:
            positions_data.append(
                {
                    "asset_name": pos.asset_name,
                    "ticker": pos.ticker,
                    "isin": pos.isin,
                    "currency": pos.currency,
                    "quantity": float(pos.quantity),
                    "unit_cost": float(pos.unit_cost),
                    "acquisition_date": pos.acquisition_date.isoformat(),
                }
            )

        return {
            "broker_name": portfolio.name,
            "positions": positions_data,
        }

    except SQLAlchemyError:
        logger.exception("Database error while retrieving user portfolio")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database persistence failed.",
        ) from None
    except Exception:
        logger.exception("Unexpected error while retrieving user portfolio")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        ) from None
