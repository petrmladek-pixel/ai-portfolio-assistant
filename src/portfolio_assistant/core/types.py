"""Custom SQLAlchemy types for database models."""

from datetime import UTC, datetime

from sqlalchemy.engine import Dialect
from sqlalchemy.types import DateTime, TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """SQLAlchemy TypeDecorator that enforces timezone-aware UTC datetimes.

    This type ensures that all datetime values stored in the database are
    timezone-aware and in UTC. Naive datetimes are converted to UTC, and
    timezone-aware datetimes are converted to UTC.

    Attributes:
        cache_ok: Set to True to allow caching of this type.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        """Process datetime before binding to database.

        Args:
            value: The datetime value to process.
            dialect: The database dialect.

        Returns:
            The datetime with UTC timezone, or None if value is None.
        """
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        """Process datetime after retrieving from database.

        Args:
            value: The datetime value from the database.
            dialect: The database dialect.

        Returns:
            The datetime with UTC timezone, or None if value is None.
        """
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
