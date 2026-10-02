"""Centralized Snowflake connection management.

Follows AGENT.md & M6.1 Hardening:
- Safe configuration loading (Password and Key-Pair authentication)
- No credential or passphrase leaking in logs or error messages
- Structured connection health diagnostics and session parameter verification
- Strict separation from UI components
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from config import SnowflakeConfig, get_config

logger = logging.getLogger(__name__)


@dataclass
class SnowflakeHealthStatus:
    storage: str = "Snowflake"
    connection: str = "NOT_CONFIGURED"
    database: Optional[str] = None
    schema: Optional[str] = None
    warehouse: Optional[str] = None
    role: Optional[str] = None
    auth_method: Optional[str] = None
    last_successful_query: Optional[datetime] = None
    latency_ms: Optional[float] = None
    error_message: Optional[str] = None


@dataclass
class SnowflakeSessionVerification:
    is_connected: bool
    auth_method: str
    database: Optional[str] = None
    schema: Optional[str] = None
    warehouse: Optional[str] = None
    role: Optional[str] = None
    user: Optional[str] = None
    version: Optional[str] = None
    latency_ms: Optional[float] = None
    error_message: Optional[str] = None
    checked_at: Optional[datetime] = None


class SnowflakeConnectionManager:
    def __init__(self, config: Optional[SnowflakeConfig] = None) -> None:
        self.config = config or get_config().snowflake
        self._connection: Any = None
        self._last_successful_query: Optional[datetime] = None
        self._last_latency_ms: Optional[float] = None

    @property
    def is_configured(self) -> bool:
        return self.config.is_configured

    def _mask_secrets(self, text: str) -> str:
        """Mask password and private key passphrase from text or error messages."""
        masked = text
        if self.config.password and self.config.password in masked:
            masked = masked.replace(self.config.password, "******")
        if self.config.private_key_passphrase and self.config.private_key_passphrase in masked:
            masked = masked.replace(self.config.private_key_passphrase, "******")
        return masked

    def load_private_key_bytes(self) -> bytes:
        """Safely load and convert PEM private key to DER PKCS8 bytes for Snowflake connector."""
        if not self.config.private_key_path:
            raise ValueError("No private key path specified in Snowflake configuration.")

        key_path = Path(self.config.private_key_path)
        if not key_path.exists():
            raise FileNotFoundError(f"Snowflake private key file not found: {key_path}")

        try:
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives import serialization

            passphrase_bytes = (
                self.config.private_key_passphrase.encode("utf-8")
                if self.config.private_key_passphrase
                else None
            )

            with open(key_path, "rb") as key_file:
                key_data = key_file.read()

            p_key = serialization.load_pem_private_key(
                key_data,
                password=passphrase_bytes,
                backend=default_backend(),
            )
            return p_key.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        except Exception as e:
            err = self._mask_secrets(str(e))
            logger.error("Failed to load Snowflake private key: %s", err)
            raise ValueError(f"Failed to load Snowflake private key: {err}") from None

    def _build_connect_params(
        self, login_timeout: int = 15, network_timeout: int = 30
    ) -> Dict[str, Any]:
        """Construct validated connect kwargs with credentials protected."""
        params: Dict[str, Any] = {
            "account": self.config.account,
            "user": self.config.user,
            "warehouse": self.config.warehouse,
            "database": self.config.database,
            "schema": self.config.schema,
            "role": self.config.role,
            "login_timeout": login_timeout,
            "network_timeout": network_timeout,
        }

        if self.config.authenticator and self.config.authenticator.lower() != "snowflake":
            params["authenticator"] = self.config.authenticator

        if self.config.private_key_path:
            params["private_key"] = self.load_private_key_bytes()
        elif self.config.password:
            params["password"] = self.config.password
        else:
            raise ValueError("Neither password nor private key is configured for Snowflake authentication.")

        return params

    def test_connection(self) -> Tuple[bool, str]:
        """Verify Snowflake connection safely without exposing secrets."""
        if not self.config.is_configured:
            return False, "Snowflake credentials not configured in environment (account/user/(password or private_key) empty)."

        try:
            import snowflake.connector  # type: ignore

            connect_params = self._build_connect_params(login_timeout=10, network_timeout=15)
            conn = snowflake.connector.connect(**connect_params)
            cur = conn.cursor()
            cur.execute("SELECT CURRENT_VERSION(), CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA()")
            row = cur.fetchone()
            cur.close()
            conn.close()
            return True, f"Connected to Snowflake successfully via {self.config.auth_method}. Version: {row[0]}, DB: {row[2]}"
        except ImportError:
            return False, "snowflake-connector-python is not installed in the current environment."
        except Exception as e:
            err_msg = self._mask_secrets(str(e))
            logger.error("Snowflake connection failed: %s", err_msg)
            return False, f"Snowflake connection failed: {err_msg}"

    def get_connection(self) -> Any:
        """Return an active connection or raise an explicit error."""
        if not self.config.is_configured:
            raise ConnectionError("Snowflake is not configured. Set environment variables to enable Snowflake backend.")

        try:
            import snowflake.connector  # type: ignore

            connect_params = self._build_connect_params(login_timeout=15, network_timeout=30)
            return snowflake.connector.connect(**connect_params)
        except ImportError:
            raise RuntimeError("snowflake-connector-python must be installed to connect to Snowflake.")
        except Exception as e:
            err_msg = self._mask_secrets(str(e))
            raise ConnectionError(f"Failed to connect to Snowflake: {err_msg}") from None

    def verify_connection(self) -> SnowflakeSessionVerification:
        """Perform a structured ping testing role, warehouse, database, schema, and session parameters."""
        now = datetime.now(timezone.utc)
        if not self.config.is_configured:
            return SnowflakeSessionVerification(
                is_connected=False,
                auth_method=self.config.auth_method,
                database=self.config.database or None,
                schema=self.config.schema or None,
                warehouse=self.config.warehouse or None,
                role=self.config.role or None,
                error_message="Snowflake credentials not configured in environment.",
                checked_at=now,
            )

        t0 = time.time()
        try:
            import snowflake.connector  # type: ignore

            connect_params = self._build_connect_params(login_timeout=10, network_timeout=15)
            conn = snowflake.connector.connect(**connect_params)
            cur = conn.cursor()
            cur.execute(
                "SELECT CURRENT_VERSION(), CURRENT_USER(), CURRENT_ROLE(), "
                "CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA()"
            )
            row = cur.fetchone()
            cur.close()
            conn.close()

            latency = round((time.time() - t0) * 1000.0, 2)
            self._last_latency_ms = latency
            self._last_successful_query = now

            return SnowflakeSessionVerification(
                is_connected=True,
                auth_method=self.config.auth_method,
                version=row[0] if row else None,
                user=row[1] if row else self.config.user,
                role=row[2] if row else self.config.role,
                warehouse=row[3] if row else self.config.warehouse,
                database=row[4] if row else self.config.database,
                schema=row[5] if row else self.config.schema,
                latency_ms=latency,
                checked_at=now,
            )
        except ImportError:
            latency = round((time.time() - t0) * 1000.0, 2)
            return SnowflakeSessionVerification(
                is_connected=False,
                auth_method=self.config.auth_method,
                database=self.config.database,
                schema=self.config.schema,
                warehouse=self.config.warehouse,
                role=self.config.role,
                latency_ms=latency,
                error_message="snowflake-connector-python is not installed in the current environment.",
                checked_at=now,
            )
        except Exception as e:
            latency = round((time.time() - t0) * 1000.0, 2)
            err_msg = self._mask_secrets(str(e))
            logger.error("Snowflake verification check failed: %s", err_msg)
            return SnowflakeSessionVerification(
                is_connected=False,
                auth_method=self.config.auth_method,
                database=self.config.database,
                schema=self.config.schema,
                warehouse=self.config.warehouse,
                role=self.config.role,
                latency_ms=latency,
                error_message=err_msg,
                checked_at=now,
            )

    def get_health_status(self) -> SnowflakeHealthStatus:
        """Run health diagnostics and return structured health status."""
        if not self.config.is_configured:
            return SnowflakeHealthStatus(
                storage="Snowflake",
                connection="NOT_CONFIGURED",
                database=self.config.database or None,
                schema=self.config.schema or None,
                warehouse=self.config.warehouse or None,
                role=self.config.role or None,
                auth_method=self.config.auth_method,
                error_message="Snowflake credentials not configured in environment.",
            )

        t0 = time.time()
        try:
            import snowflake.connector  # type: ignore

            connect_params = self._build_connect_params(login_timeout=5, network_timeout=10)
            conn = snowflake.connector.connect(**connect_params)
            cur = conn.cursor()
            cur.execute("SELECT CURRENT_DATABASE(), CURRENT_SCHEMA(), CURRENT_WAREHOUSE(), CURRENT_ROLE()")
            row = cur.fetchone()
            cur.close()
            conn.close()
            latency = (time.time() - t0) * 1000.0
            self._last_latency_ms = round(latency, 2)
            self._last_successful_query = datetime.now(timezone.utc)
            return SnowflakeHealthStatus(
                storage="Snowflake",
                connection="CONNECTED",
                database=row[0] if row else self.config.database,
                schema=row[1] if row else self.config.schema,
                warehouse=row[2] if row else self.config.warehouse,
                role=row[3] if row and len(row) > 3 else self.config.role,
                auth_method=self.config.auth_method,
                last_successful_query=self._last_successful_query,
                latency_ms=self._last_latency_ms,
            )
        except Exception as e:
            latency = (time.time() - t0) * 1000.0
            err_msg = self._mask_secrets(str(e))
            return SnowflakeHealthStatus(
                storage="Snowflake",
                connection="FAILED",
                database=self.config.database,
                schema=self.config.schema,
                warehouse=self.config.warehouse,
                role=self.config.role,
                auth_method=self.config.auth_method,
                last_successful_query=self._last_successful_query,
                latency_ms=round(latency, 2),
                error_message=err_msg,
            )
