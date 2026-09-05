"""SQLite-based ISIN cache for storing ISIN to ticker mappings.

This module provides an async SQLite cache layer for storing and retrieving
ISIN to ticker mappings with timestamps for caching purposes.
"""

import asyncio
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from portfolio_assistant.config import get_settings


class SQLiteISINCache:
    """SQLite-based cache for ISIN to ticker mappings.

    Stores mappings in a SQLite database with the following schema:
    - isin_mappings table: isin (TEXT, PRIMARY KEY), ticker (TEXT, NOT NULL),
      resolved_at (TIMESTAMP)
    """

    def __init__(self, db_path: str | None = None):
        """Initialize the SQLite ISIN cache.

        Args:
            db_path: Optional path to the SQLite database file.
                    If None, uses the default path from settings.
        """
        settings = get_settings()
        self.db_path = db_path or str(Path(settings.data_dir) / "isin_cache.db")
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Initialize the database schema if it doesn't exist."""
        # Call the sync method directly to avoid event loop conflicts
        self._create_tables_sync()

    async def _initialize_database_async(self) -> None:
        """Initialize the database schema asynchronously."""
        await asyncio.to_thread(self._create_tables_sync)

    def _create_tables_sync(self) -> None:
        """Create database tables synchronously."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS isin_mappings (
                    isin TEXT PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    resolved_at TIMESTAMP NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_isin ON isin_mappings(isin)")
            conn.commit()

    async def get_ticker(self, isin: str) -> str | None:
        """Get the cached ticker for an ISIN.

        Args:
            isin: The ISIN to look up (case-insensitive, normalized).

        Returns:
            str | None: The cached ticker if found, None otherwise.
        """
        normalized_isin = isin.strip().upper()

        def _get_ticker_sync() -> str | None:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT ticker FROM isin_mappings WHERE isin = ?",
                    (normalized_isin,),
                )
                result = cursor.fetchone()
                return result[0] if result else None

        return await asyncio.to_thread(_get_ticker_sync)

    async def set_ticker(self, isin: str, ticker: str) -> None:
        """Store an ISIN to ticker mapping in the cache.

        Args:
            isin: The ISIN to store (normalized).
            ticker: The resolved ticker symbol.
        """
        normalized_isin = isin.strip().upper()
        resolved_at = datetime.now(UTC).isoformat()

        def _set_ticker_sync() -> None:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO isin_mappings
                    (isin, ticker, resolved_at)
                    VALUES (?, ?, ?)
                    """,
                    (normalized_isin, ticker, resolved_at),
                )
                conn.commit()

        await asyncio.to_thread(_set_ticker_sync)

    async def get_all_mappings(self) -> list[tuple[str, str, str]]:
        """Get all cached ISIN to ticker mappings.

        Returns:
            list[tuple[str, str, str]]: List of (isin, ticker, resolved_at) tuples.
        """

        def _get_all_mappings_sync() -> list[tuple[str, str, str]]:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT isin, ticker, resolved_at FROM isin_mappings")
                return cursor.fetchall()

        return await asyncio.to_thread(_get_all_mappings_sync)

    async def clear_cache(self) -> None:
        """Clear all cached ISIN mappings."""

        def _clear_cache_sync() -> None:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM isin_mappings")
                conn.commit()

        await asyncio.to_thread(_clear_cache_sync)
