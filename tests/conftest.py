# tests/conftest.py
# Strict Python, no Czech diacritics in Python files.

import os

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from portfolio_assistant.core import database
from portfolio_assistant.models.db_models import Portfolio, Position  # noqa: F401
from portfolio_assistant.models.user import User  # noqa: F401

# Vynucení testovacího prostředí
os.environ["PORTFOLIO_ENVIRONMENT"] = "testing"

# ... (mock_migrations a override_settings zůstávají stejné) ...


@pytest.fixture(name="db_session")
def db_session_fixture():
    """Shared database session fixture using in-memory SQLite with StaticPool."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Force the app's engine to be the test engine
    old_engine = database.engine
    database.engine = test_engine

    SQLModel.metadata.create_all(test_engine)

    with Session(test_engine) as session:
        yield session

    # Teardown
    SQLModel.metadata.drop_all(test_engine)
    database.engine = old_engine
