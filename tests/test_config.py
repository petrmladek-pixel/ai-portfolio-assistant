# tests/conftest.py
# Strict Python, no Czech diacritics in Python files.
# All comments are strictly in English.

import os
from unittest.mock import patch

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from portfolio_assistant.config import Settings
from portfolio_assistant.core import database

# Explicitly import all db models so SQLModel registers them before create_all
from portfolio_assistant.models.db_models import Portfolio, Position  # noqa: F401
from portfolio_assistant.models.user import User  # noqa: F401

# Enforce testing environment
os.environ["PORTFOLIO_ENVIRONMENT"] = "testing"


@pytest.fixture(autouse=True)
def mock_migrations():
    """Prevent migrations from running during test sessions."""
    with patch("portfolio_assistant.main.run_db_migrations"):
        yield


@pytest.fixture
def override_settings() -> Settings:
    """Provide overridden configuration settings dedicated for testing."""
    return Settings(
        environment="testing",
        debug=True,
    )


@pytest.fixture(name="db_session")
def db_session_fixture():
    """Shared database session fixture using SQLite in-memory with StaticPool."""
    # StaticPool keeps exactly one connection open, preserving in-memory tables
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Force the app's engine to be the test engine
    old_engine = database.engine
    database.engine = test_engine

    # Create tables dynamically based on imported models
    SQLModel.metadata.create_all(test_engine)

    with Session(test_engine) as session:
        yield session

    # Teardown: drop tables and restore the original engine
    SQLModel.metadata.drop_all(test_engine)
    database.engine = old_engine
