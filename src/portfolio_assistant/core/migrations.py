"""Database migration utilities."""

import logging

from alembic.config import Config

from alembic import command

logger = logging.getLogger(__name__)


def run_db_migrations() -> None:
    """Apply all pending Alembic migrations before serving requests."""
    try:
        logger.info("Running database migrations.")
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations completed successfully.")
    except Exception:
        logger.exception("Database migrations failed.")
        raise
