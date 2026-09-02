"""Database migration utilities."""

import logging
import os

from alembic.config import Config

from alembic import command

logger = logging.getLogger("uvicorn")


def run_db_migrations() -> None:
    """Apply all pending Alembic migrations before serving requests."""
    try:
        logger.info("Running database migrations.")

        # 1. Environment variable override (highest priority)
        env_path = os.environ.get("ALEMBIC_CONFIG_PATH")
        if env_path and os.path.exists(env_path):
            ini_path = env_path
        else:
            # 2. Robust auto-discovery fallback
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
    except Exception as e:
        logger.exception(f"Database migration failed: {e}")
        raise
