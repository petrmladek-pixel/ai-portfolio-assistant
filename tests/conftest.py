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
