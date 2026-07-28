from portfolio_assistant.config import Settings, get_settings


def test_settings_load(override_settings: Settings) -> None:
    # Ensure that get_settings uses dependency_overrides or similar mechanism
    # For this example, we'll directly use the overridden settings.
    # In a real FastAPI app, you'd use FastAPI's dependency_overrides.
    settings = override_settings
    assert settings.environment == "testing"
    assert settings.debug is True


def test_get_settings_without_override() -> None:
    # Test to ensure default settings are loaded when no override is present
    settings = get_settings()
    # This is due to os.environ["ENVIRONMENT"] = "testing" in conftest.py
    assert settings.environment == "testing"
    assert settings.debug is False  # Default debug is False
