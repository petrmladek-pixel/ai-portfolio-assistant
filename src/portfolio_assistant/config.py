"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the application."""

    model_config = SettingsConfigDict(
        env_prefix="PORTFOLIO_",
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
    data_dir: str = Field(
        default="src/portfolio_assistant/data", description="Directory for data files"
    )
    gemini_api_key: str | None = Field(default=None, description="Gemini API Key")
    gemini_model: str = Field(
        default="gemini-2.5-flash", description="Default Gemini Model"
    )

    # Security settings
    secret_key: str = Field(
        default="dev-secret-key-change-me-in-production",
        description="Secret key for JWT signing",
    )
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(
        default=1440, description="JWT expiration in minutes (1440 = 1 day)"
    )
    session_cookie_name: str = Field(default="session_token", description="Cookie name")

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

        In production, security settings must be explicitly configured.
        This ensures we never run in production with default or missing credentials.

        Raises:
            ValueError: If production environment has missing security configuration
        """
        if self.environment == "production":
            if self.secret_key == "dev-secret-key-change-me-in-production":
                raise ValueError("In production, SECRET_KEY must be changed.")

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
