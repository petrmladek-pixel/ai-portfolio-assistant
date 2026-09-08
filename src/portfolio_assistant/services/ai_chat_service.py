"""Business workflow for stateful Gemini portfolio chat."""

from typing import Any

from google import genai
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from portfolio_assistant.config import get_settings
from portfolio_assistant.core.exceptions import (
    AIAnalysisError,
    PersistenceError,
    PortfolioNotFoundError,
)
from portfolio_assistant.crud import ai_chat as ai_chat_crud
from portfolio_assistant.crud import portfolio as portfolio_crud
from portfolio_assistant.models.ai import ChatMessage
from portfolio_assistant.models.allocation import PortfolioAllocationResponse
from portfolio_assistant.models.user import User
from portfolio_assistant.services.allocation import AllocationService

DEFAULT_CHAT_PROMPT = (
    "You are a careful portfolio assistant. Give educational, balanced answers "
    "about the portfolio context supplied below. Do not provide personalized "
    "investment advice. Clearly state uncertainty and encourage users to consult "
    "a qualified financial professional when appropriate."
)


class AIChatService:
    """Coordinate portfolio context, chat persistence, and Gemini responses."""

    def __init__(
        self,
        allocation_service: AllocationService | None = None,
        client: Any | None = None,
    ) -> None:
        settings = get_settings()
        self._allocation_service = allocation_service or AllocationService()
        self._model = settings.gemini_model
        self._client = client
        if self._client is None and settings.gemini_api_key:
            self._client = genai.Client(api_key=settings.gemini_api_key)

    async def handle_chat(
        self,
        db: Session,
        portfolio_id: int,
        user: User,
        user_message: str,
    ) -> str:
        """Save a user query, obtain a Gemini response, and persist that reply."""
        self._ensure_owned_portfolio(db, portfolio_id, user)
        allocations = await self._allocation_service.calculate_portfolio_allocations(
            db, portfolio_id=portfolio_id
        )
        history = ai_chat_crud.get_chat_history(db, portfolio_id, limit=10)
        self._save_message(db, portfolio_id, "user", user_message)
        response_text = await self._generate_response(
            allocations=allocations,
            custom_prompt=user.analysis_prompt,
            history=history,
            user_message=user_message,
        )
        self._save_message(db, portfolio_id, "model", response_text)
        return response_text

    @staticmethod
    def _ensure_owned_portfolio(db: Session, portfolio_id: int, user: User) -> None:
        """Ensure the supplied portfolio belongs to the requesting user."""
        if user.id is None:
            raise PortfolioNotFoundError
        portfolio = portfolio_crud.get_portfolio_for_user(db, portfolio_id, user.id)
        if portfolio is None:
            raise PortfolioNotFoundError

    @staticmethod
    def _save_message(
        db: Session,
        portfolio_id: int,
        role: str,
        content: str,
    ) -> ChatMessage:
        """Persist a message while converting database failures to domain errors."""
        try:
            return ai_chat_crud.create_chat_message(db, portfolio_id, role, content)
        except SQLAlchemyError as error:
            db.rollback()
            raise PersistenceError from error

    async def _generate_response(
        self,
        allocations: PortfolioAllocationResponse,
        custom_prompt: str | None,
        history: list[ChatMessage],
        user_message: str,
    ) -> str:
        """Request a non-empty response from Gemini using persistent history."""
        if self._client is None:
            raise AIAnalysisError("Gemini API key is not configured.")
        contents = self._build_contents(history, user_message)
        config = {
            "system_instruction": self._build_system_instruction(
                allocations, custom_prompt
            )
        }
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=contents,
                config=config,
            )
        except Exception as error:
            raise AIAnalysisError("Gemini chat request failed.") from error
        response_text = getattr(response, "text", None)
        if not isinstance(response_text, str) or not response_text.strip():
            raise AIAnalysisError("Gemini returned an empty chat response.")
        return response_text.strip()

    @staticmethod
    def _build_contents(
        history: list[ChatMessage],
        user_message: str,
    ) -> list[dict[str, Any]]:
        """Map stored messages to Gemini content entries and append the query."""
        contents = [
            {"role": message.role, "parts": [{"text": message.content}]}
            for message in history
        ]
        contents.append({"role": "user", "parts": [{"text": user_message}]})
        return contents

    @staticmethod
    def _build_system_instruction(
        allocations: PortfolioAllocationResponse,
        custom_prompt: str | None,
    ) -> str:
        """Build system instructions containing portfolio and user context."""
        prompt = custom_prompt.strip() if custom_prompt else ""
        user_prompt = prompt or DEFAULT_CHAT_PROMPT
        positions = "\n".join(
            "- {ticker}: {percentage:.2f}% | value: {value} CZK | "
            "sector: {sector} | region: {region}".format(
                ticker=item.ticker,
                percentage=item.percentage,
                value=item.market_value,
                sector=item.sector or "Unknown",
                region=item.region or "Unknown",
            )
            for item in allocations.allocations
        )
        if not positions:
            positions = "No active positions are available."
        return (
            f"{user_prompt}\n\n"
            "Portfolio context:\n"
            f"Total value: {allocations.total_value} CZK\n"
            f"Positions:\n{positions}"
        )
