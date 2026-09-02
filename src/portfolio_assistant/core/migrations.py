"""Database migration utilities."""

import logging
import os

from alembic.config import Config

from alembic import command

logger = logging.getLogger(__name__)


def run_db_migrations() -> None:
    """Apply all pending Alembic migrations before serving requests."""
    try:
        logger.info("Running database migrations.")
        ini_path = "alembic.ini"
        base_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.abspath(os.path.join(base_dir, "../../../alembic.ini")),
            os.path.abspath(os.path.join(base_dir, "../../alembic.ini")),
            os.path.abspath(os.path.join(base_dir, "../alembic.ini")),
            os.path.abspath(os.path.join(os.getcwd(), "alembic.ini")),
            "/app/alembic.ini",
            "/app/src/alembic.ini",
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                ini_path = candidate
                break

        alembic_cfg = Config(ini_path)
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations completed successfully.")
    except Exception:
        logger.exception("Database migrations failed.")
        raise
