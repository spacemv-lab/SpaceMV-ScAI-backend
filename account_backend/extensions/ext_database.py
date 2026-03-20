from typing import TYPE_CHECKING
import logging

from sqlalchemy import text

from configs import constellation_config
from models.engine import init_db
import models.engine as engine_module

from .base import Extension

if TYPE_CHECKING:
    from constellation_app import ConstellationApp


class DatabaseExtension(Extension):
    """Database extension for initializing database connection"""
    
    def init_app(self, app: "ConstellationApp") -> None:
        """Initialize database engine and session"""
        init_db(
            database_uri=constellation_config.SQLALCHEMY_DATABASE_URI,
            pool_size=constellation_config.SQLALCHEMY_POOL_SIZE,
            max_overflow=constellation_config.SQLALCHEMY_MAX_OVERFLOW
        )

        self._ensure_account_schema()

    @staticmethod
    def _ensure_account_schema() -> None:
        """Ensure account table contains required permission column."""
        if not engine_module.engine:
            return

        try:
            with engine_module.engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE account "
                        "ADD COLUMN IF NOT EXISTS coverage_analysis_permission UInt8 DEFAULT 0"
                    )
                )
        except Exception as exc:
            logging.warning("Failed to ensure account schema: %s", exc)


ext_database = DatabaseExtension()


