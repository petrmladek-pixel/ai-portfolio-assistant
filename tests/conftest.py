import os

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from portfolio_assistant.config import Settings
from portfolio_assistant.core import database

# Explicitly import all db models so SQLModel registers them before create_all
from portfolio_assistant.models.db_models import Portfolio, Position  # noqa: F401
from portfolio_assistant.models.ticker_metadata import TickerMetadata  # noqa: F401
from portfolio_assistant.models.user import User  # noqa: F401

os.environ["PORTFOLIO_ENVIRONMENT"] = "testing"


@pytest.fixture
def override_settings() -> Settings:
    """Provide overridden configuration settings dedicated for testing."""
    return Settings(
        environment="testing",
        debug=True,
        enable_demo_data=False,
    )


@pytest.fixture(name="db_session")
def db_session_fixture():
    """Provide an in-memory SQLite session that retains its schema."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    old_engine = database.engine
    database.engine = test_engine

    SQLModel.metadata.create_all(test_engine)
    try:
        with Session(test_engine) as session:
            yield session
    finally:
        SQLModel.metadata.drop_all(test_engine)
        database.engine = old_engine
