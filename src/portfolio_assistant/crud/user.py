"""Database operations for users."""

from sqlmodel import Session, select

from portfolio_assistant.models.user import User


def get_user_by_email(session: Session, email: str) -> User | None:
    """Return the user with the given email address, if it exists."""
    statement = select(User).where(User.email == email)
    return session.exec(statement).first()


def create_user(session: Session, user: User) -> User:
    """Persist and refresh a user."""
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
