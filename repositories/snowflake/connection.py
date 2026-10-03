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
import threading
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


class _PooledConnectionProxy:
    """Lightweight connection proxy that keeps the physical Snowflake connection alive across queries."""

    def __init__(self, real_conn: Any, manager: SnowflakeConnectionManager) -> None:
        self._real_conn = real_conn
        self._manager = manager

    def cursor(self, *args: Any, **kwargs: Any) -> Any:
        return self._real_conn.cursor(*args, **kwargs)

    def commit(self) -> None:
        self._real_conn.commit()

    def rollback(self) -> None:
        self._real_conn.rollback()

    def close(self) -> None:
        # Prevent premature socket termination across queries
        pass

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real_conn, name)


class SnowflakeConnectionManager:
    def __init__(self, config: Optional[SnowflakeConfig] = None) -> None:
        self.config = config or get_config().snowflake
        self._connection: Any = None
        self._lock = threading.Lock()
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
        self, login_timeout: int = 15, network_timeout: int = 30, include_database: bool = True
    ) -> Dict[str, Any]:
        """Construct validated connect kwargs with credentials protected.
        
        When include_database=False, omits database and schema from connection parameters,
        allowing bootstrap connection to clean Snowflake accounts where the database does not yet exist.
        """
        params: Dict[str, Any] = {
            "account": self.config.account,
            "user": self.config.user,
            "warehouse": self.config.warehouse,
            "role": self.config.role,
            "login_timeout": login_timeout,
            "network_timeout": network_timeout,
        }

        if include_database:
            if self.config.database:
                params["database"] = self.config.database
            if self.config.schema:
                params["schema"] = self.config.schema

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

    def _create_new_connection(self, bootstrap: bool = False) -> Any:
        try:
            import snowflake.connector  # type: ignore

            connect_params = self._build_connect_params(
                login_timeout=15, network_timeout=30, include_database=not bootstrap
            )
            return snowflake.connector.connect(**connect_params)
        except ImportError:
            raise RuntimeError("snowflake-connector-python must be installed to connect to Snowflake.")
        except Exception as e:
            err_msg = self._mask_secrets(str(e))
            raise ConnectionError(f"Failed to connect to Snowflake: {err_msg}") from None

    def get_connection(self, bootstrap: bool = False) -> Any:
        """Return an active connection or raise an explicit error.

        When bootstrap=True, connects without specifying database/schema at handshake time,
        allowing administrative bootstrap (CREATE DATABASE / CREATE SCHEMA) on a clean account.
        """
        if not self.config.is_configured:
            raise ConnectionError("Snowflake is not configured. Set environment variables to enable Snowflake backend.")

        if bootstrap:
            return self._create_new_connection(bootstrap=True)

        with self._lock:
            if self._connection is not None:
                try:
                    is_closed_fn = getattr(self._connection, "is_closed", None)
                    if is_closed_fn and not is_closed_fn():
                        return _PooledConnectionProxy(self._connection, self)
                    elif is_closed_fn is None:
                        return _PooledConnectionProxy(self._connection, self)
                except Exception:
                    self._connection = None

            self._connection = self._create_new_connection(bootstrap=False)
            return _PooledConnectionProxy(self._connection, self)

    def close(self) -> None:
        """Explicitly terminate physical pooled connection."""
        with self._lock:
            if self._connection is not None:
                try:
                    self._connection.close()
                except Exception:
                    pass
                self._connection = None

    def get_bootstrap_connection(self) -> Any:
        """Return an active connection without requiring database/schema context to already exist."""
        return self.get_connection(bootstrap=True)

    def verify_connection(self, bootstrap: bool = False) -> SnowflakeSessionVerification:
        """Perform a structured ping testing role, warehouse, database, schema, and session parameters."""
        return self.verify_session(bootstrap=bootstrap)

    def verify_session(self, bootstrap: bool = False) -> SnowflakeSessionVerification:
        """Perform a structured ping testing role, warehouse, database, schema, and session parameters.
        
        When bootstrap=True, connects at account-level without database/schema parameters,
        verifying that credentials, role, and warehouse are valid before database creation.
        """
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

            connect_params = self._build_connect_params(
                login_timeout=10, network_timeout=15, include_database=not bootstrap
            )
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
                database=row[4] if row else None,
                schema=row[5] if row else None,
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
