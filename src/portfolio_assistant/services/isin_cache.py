import asyncio
import sqlite3
from datetime import datetime
from pathlib import Path


class SQLiteISINCache:
    """Caching layer for ISIN-to-ticker mappings using SQLite."""

    def __init__(self, db_path: str = "data/isin_cache.db") -> None:
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initializes the database and creates the isin_mappings table."""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS isin_mappings (
                    isin TEXT PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    resolved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    async def get(self, isin: str) -> str | None:
        """Retrieves a ticker mapping for the given ISIN from the cache.

        Args:
            isin (str): The ISIN to look up.

        Returns:
            Optional[str]: The cached ticker or None if not found.
        """
        normalized_isin = isin.strip().upper()
        return await asyncio.to_thread(self._get_sync, normalized_isin)

    def _get_sync(self, isin: str) -> str | None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT ticker FROM isin_mappings WHERE isin = ?", (isin,)
            )
            row = cursor.fetchone()
            return row[0] if row else None

    async def set(self, isin: str, ticker: str) -> None:
        """Saves a ticker mapping for the given ISIN to the cache.

        Args:
            isin (str): The ISIN.
            ticker (str): The resolved ticker symbol.
        """
        normalized_isin = isin.strip().upper()
        normalized_ticker = ticker.strip().upper()
        await asyncio.to_thread(self._set_sync, normalized_isin, normalized_ticker)

    def _set_sync(self, isin: str, ticker: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO isin_mappings (isin, ticker, resolved_at)
                VALUES (?, ?, ?)
                """,
                (isin, ticker, datetime.now().isoformat()),
            )
