"""Database migrations helper using Alembic."""

import logging
import os

from alembic.config import Config

from alembic import command

logger = logging.getLogger(__name__)


def run_db_migrations() -> None:
    """Run database migrations programmatically using Alembic."""
    # Read the configuration path from the environment variable (best practice)
    # Fallback to a single, explicit default path "alembic.ini"
    ini_path = os.environ.get("ALEMBIC_CONFIG_PATH", "alembic.ini")

    # Resolve to absolute path to prevent working directory issues
    abs_ini_path = os.path.abspath(ini_path)

    # Fail-fast: raise a clear FileNotFoundError if the config file is missing
    if not os.path.exists(abs_ini_path):
        raise FileNotFoundError(
            f"Alembic configuration file not found at: {abs_ini_path}. "
            "Please configure the 'ALEMBIC_CONFIG_PATH' environment "
            "variable with the correct absolute path to your alembic.ini."
        )

    try:
        logger.info(f"Running database migrations with config: {abs_ini_path}")
        alembic_cfg = Config(abs_ini_path)
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations completed successfully.")
    except Exception as e:
        # Log the full exception traceback for production monitoring
        logger.exception(f"Database migration failed: {e}")
        raise
