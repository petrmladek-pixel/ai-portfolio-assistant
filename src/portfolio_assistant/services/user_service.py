"""HTTP-independent workflows for users."""

from sqlmodel import Session

from portfolio_assistant.core.exceptions import (
    InactiveUserError,
    InvalidCredentialsError,
    PersistenceError,
    UserAlreadyExistsError,
)
from portfolio_assistant.core.security import hash_password, verify_password
from portfolio_assistant.crud.user import create_user, get_user_by_email
from portfolio_assistant.models.user import User, UserCreate
from portfolio_assistant.services.portfolio_service import PortfolioService


class UserService:
    """Coordinate user registration and authentication."""

    def __init__(self, portfolio_service: PortfolioService | None = None) -> None:
        """Initialize user workflows with portfolio provisioning support."""
        self.portfolio_service = portfolio_service or PortfolioService()

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
        try:
            created_user = create_user(session, user)
            self.portfolio_service.ensure_default_portfolio(
                session, self._user_id(created_user)
            )
            return created_user
        except Exception:
            session.rollback()
            raise

    def authenticate(self, session: Session, user_data: UserCreate) -> User:
        """Validate credentials and return the active user."""
        user = get_user_by_email(session, user_data.email)
        if user is None or not verify_password(
            user_data.password, user.hashed_password
        ):
            raise InvalidCredentialsError
        if not user.is_active:
            raise InactiveUserError
        self.portfolio_service.ensure_default_portfolio(session, self._user_id(user))
        return user

    def _user_id(self, user: User) -> int:
        """Return a persisted user's identifier."""
        if user.id is None:
            raise PersistenceError
        return user.id
