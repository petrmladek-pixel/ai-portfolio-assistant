"""Core utility functions for the portfolio assistant application."""

import datetime


def get_now_utc() -> datetime.datetime:
    """Return the current datetime in UTC timezone.

    Returns:
        datetime.datetime: Current datetime with UTC timezone information.
    """
    return datetime.datetime.now(datetime.timezone.utc)  # noqa: UP017
