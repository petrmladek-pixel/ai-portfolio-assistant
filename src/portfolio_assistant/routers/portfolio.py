"""Portfolio persistence and retrieval router."""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from ..core.database import get_db_session
from ..dependencies import get_current_user
from ..models.db_models import Portfolio
from ..models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/me")
async def get_my_portfolio(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """
    Fetch the saved positions from the database for the logged-in user.
    """
    try:
        # Find the portfolio for the logged-in user
        statement = select(Portfolio).where(Portfolio.owner_id == current_user.id)
        portfolio = session.exec(statement).first()

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

    except Exception as e:
        logger.exception("Failed to retrieve user portfolio")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve portfolio: {str(e)}",
        ) from e
