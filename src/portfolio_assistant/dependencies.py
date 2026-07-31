"""Global dependencies for the portfolio assistant application."""

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from portfolio_assistant.config import get_settings

# Security setup for Basic Authentication
security = HTTPBasic()


def verify_credentials(
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
) -> str:
    """
    Verify basic authentication credentials against configuration settings.

    Uses secrets.compare_digest to prevent timing attacks.
    In production, credentials must be explicitly configured
    (enforced by Pydantic validator).
    In non-production environments, falls back to "admin"/"admin" for local testing.

    Args:
        credentials: HTTPBasicCredentials from FastAPI security dependency

    Returns:
        str: The authenticated username

    Raises:
        HTTPException: 401 Unauthorized if credentials are invalid
    """
    settings = get_settings()

    # Retrieve expected values from configuration
    expected_username = settings.web_basic_auth_username
    expected_password = settings.web_basic_auth_password

    # For non-production environments, allow fallback to "admin"/"admin" for
    # easy local testing
    # Production environments are already guarded by Pydantic validator to ensure
    # explicit configuration
    if settings.environment != "production":
        expected_username = expected_username or "admin"
        expected_password = expected_password or "admin"
    else:
        # In production, these should never be None due to Pydantic validation,
        # but we provide a safety net to ensure they're always strings
        expected_username = expected_username or ""
        expected_password = expected_password or ""

    # Use secrets.compare_digest to prevent timing attacks
    is_correct_username = secrets.compare_digest(
        credentials.username, str(expected_username)
    )
    is_correct_password = secrets.compare_digest(
        credentials.password, str(expected_password)
    )

    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
