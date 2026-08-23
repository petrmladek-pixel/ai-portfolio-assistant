"""HTTP-independent workflows for users."""

from sqlmodel import Session

from portfolio_assistant.core.exceptions import (
    InactiveUserError,
    InvalidCredentialsError,
    UserAlreadyExistsError,
)
from portfolio_assistant.core.security import hash_password, verify_password
from portfolio_assistant.crud.user import create_user, get_user_by_email
from portfolio_assistant.models.user import User, UserCreate


class UserService:
    """Coordinate user registration and authentication."""

    def register(self, session: Session, user_data: UserCreate) -> User:
        """Create a user unless its email address is already registered."""
        if get_user_by_email(session, user_data.email) is not None:
            raise UserAlreadyExistsError
        user = User(
            email=user_data.email,
            hashed_password=hash_password(user_data.password),
            full_name=user_data.full_name,
            is_active=user_data.is_active,
            is_superuser=user_data.is_superuser,
        )
        return create_user(session, user)

    def authenticate(self, session: Session, user_data: UserCreate) -> User:
        """Validate credentials and return the active user."""
        user = get_user_by_email(session, user_data.email)
        if user is None or not verify_password(
            user_data.password, user.hashed_password
        ):
            raise InvalidCredentialsError
        if not user.is_active:
            raise InactiveUserError
        return user
