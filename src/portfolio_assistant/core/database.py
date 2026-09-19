from collections.abc import Generator
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from portfolio_assistant.config import get_settings

SQLMODEL_DATABASE_URL = get_settings().database_url


def create_database_engine(database_url: str) -> Engine:
    """Create an engine with SQLite foreign-key enforcement enabled."""
    database_engine = create_engine(database_url)
    if database_url.startswith("sqlite"):
        event.listen(database_engine, "connect", _enable_sqlite_foreign_keys)
    return database_engine


def _enable_sqlite_foreign_keys(
    dbapi_connection: Any,
    connection_record: Any,
) -> None:
    """Enable foreign-key checks for every SQLite connection."""
    del connection_record
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


engine = create_database_engine(SQLMODEL_DATABASE_URL)


def get_db_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
