"""Authentication routes for the application."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session, select

from ..config import get_settings
from ..core.database import get_db_session
from ..core.security import create_access_token, hash_password, verify_password
from ..models.user import User, UserCreate, UserPublic

settings = get_settings()
router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post(
    "/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED
)
def register(
    user_in: UserCreate,
    session: Annotated[Session, Depends(get_db_session)],
) -> User:
    """Register a new user."""
    # Check if user already exists
    statement = select(User).where(User.email == user_in.email)
    existing_user = session.exec(statement).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )

    # Hash password and create user
    hashed_password = hash_password(user_in.password)
    user = User(
        email=user_in.email,
        hashed_password=hashed_password,
        full_name=user_in.full_name,
        is_active=user_in.is_active,
        is_superuser=user_in.is_superuser,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.post("/login")
def login(
    user_in: UserCreate,  # Using UserCreate for simplicity, typically
    # would use OAuth2PasswordRequestForm
    session: Annotated[Session, Depends(get_db_session)],
    response: Response,
) -> dict[str, str]:
    """Log in a user and set session cookie."""
    statement = select(User).where(User.email == user_in.email)
    user = session.exec(statement).first()

    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is inactive",
        )

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
