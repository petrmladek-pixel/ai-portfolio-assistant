"""Portfolio persistence and retrieval router."""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from portfolio_assistant.core.exceptions import (
    InvalidImportTypeError,
    PersistenceError,
    PortfolioImportError,
    PortfolioNotFoundError,
)
from portfolio_assistant.models.portfolio import PortfolioCreate

from ..core.database import get_db_session
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
    """Fetch the saved positions from the database for the logged-in user."""
    user_id = get_persisted_user_id(current_user)
    try:
        portfolio = portfolio_crud.get_first_portfolio_for_user(session, user_id)
        if not portfolio:
            return {"broker_name": "None", "positions": []}

        positions_data = [
            {
                "asset_name": pos.asset_name,
                "ticker": pos.ticker,
                "isin": pos.isin,
                "currency": pos.currency,
                "quantity": float(pos.quantity),
                "unit_cost": float(pos.unit_cost),
                "acquisition_date": pos.acquisition_date.isoformat(),
            }
            for pos in portfolio.positions
        ]
        return {"broker_name": portfolio.name, "positions": positions_data}
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


@router.post("/import", status_code=status.HTTP_200_OK)
async def import_portfolio(
    portfolio_id: Annotated[int, Form()],
    import_type: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service)],
) -> dict[str, Any]:
    """Import portfolio positions from an uploaded CSV file."""
    user_id = get_persisted_user_id(current_user)
    try:
        await portfolio_service.process_portfolio_import(
            session, user_id, portfolio_id, import_type, file
        )
        return {
            "status": "success",
            "message": "Positions successfully imported.",
        }
    except PortfolioNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found.",
        ) from None
    except InvalidImportTypeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported import type.",
        ) from None
    except PersistenceError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database persistence failed.",
        ) from None
    except PortfolioImportError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from None
    except Exception:
        logger.exception("Unexpected error during portfolio import")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        ) from None
