"""Core utility functions for the portfolio assistant application."""

from datetime import UTC, datetime


def get_now_utc() -> datetime:
    """Return the current datetime in UTC timezone.

    Returns:
        datetime: Current datetime with UTC timezone information.
    """
    return datetime.now(UTC)
