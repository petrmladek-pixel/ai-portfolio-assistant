"""AI analysis and chat message models for portfolio insights."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator
from pydantic import Field as PydanticField
from sqlmodel import Field, SQLModel

from portfolio_assistant.core.types import UTCDateTime
from portfolio_assistant.core.utils import get_now_utc


class PortfolioAnalysisResponse(BaseModel):
    """Public representation of a cached portfolio analysis."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    portfolio_id: int
    rating_score: int
    analysis_content: str
    created_at: datetime


class ChatMessageResponse(BaseModel):
    """Public representation of one stored chat message."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    portfolio_id: int
    role: str
    content: str
    created_at: datetime


class ChatRequest(BaseModel):
    """Payload for a portfolio chat request."""

    message: str = PydanticField(min_length=1)


class ChatResponse(BaseModel):
    """Assistant response to a portfolio chat request."""

    message: str


class PromptResponse(BaseModel):
    """Current custom AI system prompt for the authenticated user."""

    prompt: str | None


class PromptUpdateRequest(BaseModel):
    """Payload for changing the current user's custom AI system prompt."""

    prompt: str


class PortfolioAnalysisBase(SQLModel):
    """Base fields for portfolio analysis cache."""

    portfolio_id: int = Field(foreign_key="portfolios.id", index=True)
    rating_score: int = Field(ge=1, le=100)
    analysis_content: str


class PortfolioAnalysis(PortfolioAnalysisBase, table=True):
    """Database model for cached portfolio AI analysis reports."""

    __tablename__ = "portfolio_analyses"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        default_factory=get_now_utc,
        nullable=False,
        sa_type=UTCDateTime,
    )


class PortfolioAIAnalysis(SQLModel, table=True):
    """Persona-aware cached Markdown report for a portfolio."""

    __tablename__ = "portfolio_ai_analyses"

    id: int | None = Field(default=None, primary_key=True)
    portfolio_id: int = Field(foreign_key="portfolios.id", index=True)
    analysis_text: str
    persona_id: str = Field(default="WARREN_BUFFETT", index=True)
    user_context: str | None = Field(default=None)
    portfolio_hash: str
    created_at: datetime = Field(
        default_factory=get_now_utc,
        nullable=False,
        sa_type=UTCDateTime,
    )


class AIAnalysisRequest(BaseModel):
    """Payload for a persona-aware portfolio AI analysis."""

    persona_id: str = "WARREN_BUFFETT"
    user_context: str | None = PydanticField(default=None, max_length=2000)
    force_refresh: bool = False


class AIAnalysisResponse(BaseModel):
    """Result of a persona-aware portfolio AI analysis."""

    analysis_text: str
    persona_id: str
    cached: bool
    created_at: datetime


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
    created_at: datetime = Field(
        default_factory=get_now_utc,
        nullable=False,
        sa_type=UTCDateTime,
    )
