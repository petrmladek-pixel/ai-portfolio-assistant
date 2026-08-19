"""Global pytest configuration and shared test fixtures."""

import os

import pytest

from portfolio_assistant.config import Settings

# Vynucení testovacího prostředí
os.environ["PORTFOLIO_ENVIRONMENT"] = "testing"


@pytest.fixture
def override_settings() -> Settings:
    """Provide overridden configuration settings dedicated for testing."""
    return Settings(
        environment="testing",
        debug=True,
    )


@pytest.fixture(name="db_session")
def db_session_fixture():
    """Shared database session fixture."""
    from sqlmodel import Session, SQLModel

    from portfolio_assistant.core.database import engine

    # Setup - Ensure data directory exists
    os.makedirs("./data", exist_ok=True)
    # Setup - Use SQLModel to create tables
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    # Teardown - Drop tables after test
    SQLModel.metadata.drop_all(engine)
