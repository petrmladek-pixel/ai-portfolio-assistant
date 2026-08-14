from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlmodel import Column, Field, Numeric, Relationship, SQLModel

if TYPE_CHECKING:
    from .user import User


class PortfolioBase(SQLModel):
    name: str = Field(index=True)
    description: str | None = None
    owner_id: int | None = Field(default=None, foreign_key="user.id")


class Portfolio(PortfolioBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

    positions: list["Position"] = Relationship(back_populates="portfolio")
    owner: Optional["User"] = Relationship(back_populates="portfolios")


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
