# Strict Python, no Czech diacritics in Python files.
# All comments are strictly in English.

from portfolio_assistant.config import get_settings


def test_settings_load(override_settings):
    """Test that configuration settings load correctly with override."""
    assert override_settings.environment == "testing"
    assert override_settings.enable_demo_data is False


def test_get_settings_without_override():
    """Test that get_settings loads default settings correctly."""
    settings = get_settings()
    assert settings is not None
    assert isinstance(settings.enable_demo_data, bool)
