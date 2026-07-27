"""Global pytest configuration and shared test fixtures."""

import os

import pytest

from python_template_uv.config import Settings

# Vynucení testovacího prostředí
os.environ["ENVIRONMENT"] = "testing"


@pytest.fixture
def override_settings() -> Settings:
    """Provide overridden configuration settings dedicated for testing."""
    return Settings(
        environment="testing",
        debug=True,
    )
