"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Basic settings
    app_name: str = Field(default="python_template_uv", description="Application name")
    environment: Literal["development", "testing", "staging", "production"] = Field(
        default="development", description="Runtime environment"
    )
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging output level")

    # Database and keys
    database_url: str = Field(
        default="sqlite:///./app.db", description="Database connection URI"
    )
    gemini_api_key: str | None = Field(default=None, description="Gemini API Key")
    gemini_model: str = Field(
        default="gemini-2.5-flash", description="Default Gemini Model"
    )

    # Web Basic Authentication
    web_basic_auth_username: str | None = Field(
        default=None, description="Username for web dashboard basic authentication"
    )
    web_basic_auth_password: str | None = Field(
        default=None, description="Password for web dashboard basic authentication"
    )

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """
        Fail-closed validation for production environment.

        In production, basic authentication credentials must be explicitly configured.
        This ensures we never run in production with default or missing credentials.

        Raises:
            ValueError: If production environment has missing basic auth credentials
        """
        if self.environment == "production":
            if not self.web_basic_auth_username or not self.web_basic_auth_password:
                raise ValueError(
                    "In production, WEB_BASIC_AUTH_USERNAME and "
                    "WEB_BASIC_AUTH_PASSWORD must be explicitly configured."
                )
            if (
                not self.web_basic_auth_username.strip()
                or not self.web_basic_auth_password.strip()
            ):
                raise ValueError(
                    "In production, WEB_BASIC_AUTH_USERNAME and WEB_BASIC_AUTH_PASSWORD"
                    " cannot be empty strings."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    """Load and cache settings for the lifetime of the process."""
    return Settings()
