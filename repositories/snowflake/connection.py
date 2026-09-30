"""Centralized Snowflake connection management.

Follows AGENT.md:
- Safe configuration loading
- No credential leaking in logs or error messages
- Graceful connection testing
- Separation from UI components
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Tuple

from config import SnowflakeConfig, get_config

logger = logging.getLogger(__name__)


class SnowflakeConnectionManager:
    def __init__(self, config: Optional[SnowflakeConfig] = None) -> None:
        self.config = config or get_config().snowflake
        self._connection: Any = None

    @property
    def is_configured(self) -> bool:
        return self.config.is_configured

    def test_connection(self) -> Tuple[bool, str]:
        """Verify Snowflake connection safely without exposing secrets."""
        if not self.config.is_configured:
            return False, "Snowflake credentials not configured in environment (account/user/password empty)."

        try:
            import snowflake.connector  # type: ignore

            conn = snowflake.connector.connect(
                account=self.config.account,
                user=self.config.user,
                password=self.config.password,
                warehouse=self.config.warehouse,
                database=self.config.database,
                schema=self.config.schema,
                role=self.config.role,
                login_timeout=10,
            )
            cur = conn.cursor()
            cur.execute("SELECT CURRENT_VERSION(), CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA()")
            row = cur.fetchone()
            cur.close()
            conn.close()
            return True, f"Connected to Snowflake successfully. Version: {row[0]}, DB: {row[2]}"
        except ImportError:
            return False, "snowflake-connector-python is not installed in the current environment."
        except Exception as e:
            # Mask any credentials from exception string
            err_msg = str(e).replace(self.config.password, "******") if self.config.password else str(e)
            logger.error("Snowflake connection failed: %s", err_msg)
            return False, f"Snowflake connection failed: {err_msg}"

    def get_connection(self) -> Any:
        """Return an active connection or raise an explicit error."""
        if not self.config.is_configured:
            raise ConnectionError("Snowflake is not configured. Set environment variables to enable Snowflake backend.")

        try:
            import snowflake.connector  # type: ignore

            return snowflake.connector.connect(
                account=self.config.account,
                user=self.config.user,
                password=self.config.password,
                warehouse=self.config.warehouse,
                database=self.config.database,
                schema=self.config.schema,
                role=self.config.role,
            )
        except ImportError:
            raise RuntimeError("snowflake-connector-python must be installed to connect to Snowflake.")
        except Exception as e:
            err_msg = str(e).replace(self.config.password, "******") if self.config.password else str(e)
            raise ConnectionError(f"Failed to connect to Snowflake: {err_msg}") from None
