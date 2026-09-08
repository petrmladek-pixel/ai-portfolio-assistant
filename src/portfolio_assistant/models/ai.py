"""AI analysis and chat message models for portfolio insights."""

from datetime import datetime

from pydantic import field_validator
from sqlmodel import Field, SQLModel


class PortfolioAnalysisBase(SQLModel):
    """Base fields for portfolio analysis cache."""

    portfolio_id: int = Field(foreign_key="portfolios.id", index=True)
    rating_score: int = Field(ge=1, le=100)
    analysis_content: str


class PortfolioAnalysis(PortfolioAnalysisBase, table=True):
    """Database model for cached portfolio AI analysis reports."""

    __tablename__ = "portfolio_analyses"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ChatMessageBase(SQLModel):
    """Base fields for chat messages."""

    portfolio_id: int = Field(foreign_key="portfolios.id", index=True)
    role: str
    content: str

    @field_validator("role", mode="before")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate that role is either user or model."""
        if v not in ("user", "model"):
            raise ValueError("Role must be 'user' or 'model'")
        return v


class ChatMessage(ChatMessageBase, table=True):
    """Database model for persistent chat messages with Gemini."""

    __tablename__ = "chat_messages"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
