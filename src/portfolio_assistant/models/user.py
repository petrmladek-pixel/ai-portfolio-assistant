from typing import TYPE_CHECKING

from pydantic import Field as PydanticField
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .db_models import Portfolio


class UserBase(SQLModel):
    email: str = Field(unique=True, index=True)
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    full_name: str | None = Field(default=None)


class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    hashed_password: str

    portfolios: list["Portfolio"] = Relationship(back_populates="owner")


class UserCreate(UserBase):
    password: str = PydanticField(min_length=8, max_length=100)


class UserPublic(UserBase):
    id: int
