"""Stateless database operations for persistent AI chat messages."""

from sqlmodel import Session, col, select

from portfolio_assistant.models.ai import ChatMessage

_VALID_ROLES = frozenset({"user", "model"})


def get_chat_history(
    db: Session,
    portfolio_id: int,
    limit: int = 10,
) -> list[ChatMessage]:
    """Return the most recent portfolio messages in chronological order."""
    if limit < 1:
        return []
    statement = (
        select(ChatMessage)
        .where(ChatMessage.portfolio_id == portfolio_id)
        .order_by(col(ChatMessage.created_at).desc())
        .limit(limit)
    )
    messages = list(db.exec(statement).all())
    messages.reverse()
    return messages


def create_chat_message(
    db: Session,
    portfolio_id: int,
    role: str,
    content: str,
) -> ChatMessage:
    """Persist and refresh one portfolio chat message."""
    if role not in _VALID_ROLES:
        raise ValueError("Role must be 'user' or 'model'.")
    message = ChatMessage(
        portfolio_id=portfolio_id,
        role=role,
        content=content,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message
