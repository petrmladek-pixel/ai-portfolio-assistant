"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
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


@lru_cache
def get_settings() -> Settings:
    """Load and cache settings for the lifetime of the process."""
    return Settings()
