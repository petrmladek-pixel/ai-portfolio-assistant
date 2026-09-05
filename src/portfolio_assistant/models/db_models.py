from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlmodel import Column, Field, Numeric, Relationship, SQLModel

from portfolio_assistant.models.portfolio import TransactionType

if TYPE_CHECKING:
    from .user import User


class PortfolioBase(SQLModel):
    name: str = Field(index=True)
    broker: str = Field(index=True)
    description: str | None = None
    user_id: int | None = Field(default=None, foreign_key="user.id")


class Portfolio(PortfolioBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

    positions: list["Position"] = Relationship(back_populates="portfolio")
    user: Optional["User"] = Relationship(back_populates="portfolios")


class PositionBase(SQLModel):
    asset_name: str
    ticker: str
    isin: str | None = None
    currency: str
    quantity: Decimal = Field(
        sa_column=Column(Numeric(precision=18, scale=8, asdecimal=True))
    )
    unit_cost: Decimal = Field(
        sa_column=Column(Numeric(precision=18, scale=8, asdecimal=True))
    )
    acquisition_date: date
    portfolio_id: int | None = Field(default=None, foreign_key="portfolio.id")


class Position(PositionBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

    portfolio: Portfolio | None = Relationship(back_populates="positions")


class Transaction(SQLModel, table=True):
    """Represents a portfolio trade used to calculate current holdings."""

    id: int | None = Field(default=None, primary_key=True)
    ticker: str = Field(index=True)
    quantity: Decimal = Field(
        sa_column=Column(Numeric(precision=18, scale=8, asdecimal=True))
    )
    transaction_type: TransactionType
    portfolio_id: int = Field(foreign_key="portfolio.id", index=True)
