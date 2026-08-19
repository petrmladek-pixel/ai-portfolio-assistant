"""Global dependencies for the portfolio assistant application."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session

from portfolio_assistant.config import get_settings
from portfolio_assistant.core.database import get_db_session
from portfolio_assistant.core.security import get_current_user as security_get_user
from portfolio_assistant.models.user import User


async def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db_session)],
) -> User:
    """
    Get the current authenticated user from a secure HttpOnly cookie.

    Args:
        request: FastAPI request object
        db: Database session

    Returns:
        User: The authenticated user object

    Raises:
        HTTPException: 401 if not authenticated or user not found
    """
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please log in.",
        )

    # We reuse the core security implementation
    return await security_get_user(request, db)


async def get_optional_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db_session)],
) -> User | None:
    """
    Get the current authenticated user from a secure HttpOnly cookie, or None
    if not authenticated.
    """
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)

    if not token:
        return None

    return await security_get_user(request, db)
