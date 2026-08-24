"""Authentication routes for the application."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session

from ..config import get_settings
from ..core.database import get_db_session
from ..core.exceptions import (
    InactiveUserError,
    InvalidCredentialsError,
    UserAlreadyExistsError,
)
from ..core.security import create_access_token
from ..models.user import User, UserCreate, UserPublic
from ..services.user_service import UserService

settings = get_settings()
router = APIRouter(prefix="/api/auth", tags=["authentication"])


def get_user_service() -> UserService:
    """Provide the user workflow service."""
    return UserService()


@router.post(
    "/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED
)
def register(
    user_in: UserCreate,
    session: Annotated[Session, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> User:
    """Register a new user."""
    try:
        return user_service.register(session, user_in)
    except UserAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        ) from None


@router.post("/login")
def login(
    user_in: UserCreate,  # Using UserCreate for simplicity, typically
    # would use OAuth2PasswordRequestForm
    session: Annotated[Session, Depends(get_db_session)],
    response: Response,
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> dict[str, str]:
    """Log in a user and set session cookie."""
    try:
        user = user_service.authenticate(session, user_in)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        ) from None
    except InactiveUserError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is inactive",
        ) from None

    # Create access token
    access_token = create_access_token(data={"sub": user.email})

    # Set HttpOnly cookie
    response.set_cookie(
        key=settings.session_cookie_name,
        value=access_token,
        httponly=True,
        max_age=settings.access_token_expire_minutes * 60,
        expires=settings.access_token_expire_minutes * 60,
        samesite="lax",
        secure=settings.environment == "production",
    )

    return {"message": "Successfully logged in"}


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    """Log out a user by clearing the session cookie."""
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        samesite="lax",
        secure=settings.environment == "production",
    )
    return {"message": "Successfully logged out"}
