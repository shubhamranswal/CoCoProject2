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


def is_session_expired_error(exc: Optional[BaseException]) -> bool:
    """Determine whether an exception is caused by session expiration or ReauthenticationRequest."""
    if exc is None:
        return False

    cls_name = exc.__class__.__name__
    if "reauthentication" in cls_name.lower():
        return True

    # Snowflake error codes indicating session or authentication expiration
    expired_codes = {
        252007,  # ER_FAILED_TO_RENEW_SESSION
        390110,  # ID_TOKEN_EXPIRED_GS_CODE
        390112,  # SESSION_EXPIRED_GS_CODE
        390113,  # MASTER_TOKEN_NOTFOUND_GS_CODE
        390114,  # MASTER_TOKEN_EXPIRED_GS_CODE
        390115,  # MASTER_TOKEN_INVALD_GS_CODE
        390195,  # ID_TOKEN_INVALID_LOGIN_REQUEST_GS_CODE
        390318,  # OAUTH_ACCESS_TOKEN_EXPIRED_GS_CODE
        390400,  # BAD_REQUEST_GS_CODE (during renew)
        "252007",
        "390110",
        "390112",
        "390113",
        "390114",
        "390115",
        "390195",
        "390318",
        "390400",
    }
    errno = getattr(exc, "errno", None) or getattr(exc, "code", None)
    if errno in expired_codes:
        return True

    msg = str(getattr(exc, "msg", "") or str(exc)).lower()
    session_keywords = (
        "reauthenticationrequest",
        "reauthentication",
        "renew_session",
        "failed to renew session",
        "session has expired",
        "session no longer exists",
        "session expired",
        "session is closed",
        "master token expired",
        "token has expired",
        "token is invalid",
        "id token expired",
    )
    if any(kw in msg for kw in session_keywords):
        return True

    cause = getattr(exc, "cause", None) or getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
    if cause is not None and cause is not exc:
        return is_session_expired_error(cause)

    return False


class _PooledCursorProxy:
    """Cursor proxy that intercepts queries and automatically retries once on session expiration."""

    def __init__(self, real_cursor: Any, conn_proxy: _PooledConnectionProxy) -> None:
        self._real_cursor = real_cursor
        self._conn_proxy = conn_proxy

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        try:
            return self._real_cursor.execute(*args, **kwargs)
        except Exception as exc:
            if is_session_expired_error(exc):
                logger.warning(
                    "Snowflake session expired or ReauthenticationRequest detected (%s). "
                    "Resetting connection and retrying operation once...",
                    type(exc).__name__,
                )
                new_conn = self._conn_proxy._manager.reconnect()
                self._conn_proxy._real_conn = new_conn
                self._real_cursor = new_conn.cursor()
                return self._real_cursor.execute(*args, **kwargs)
            raise

    def executemany(self, *args: Any, **kwargs: Any) -> Any:
        try:
            return self._real_cursor.executemany(*args, **kwargs)
        except Exception as exc:
            if is_session_expired_error(exc):
                logger.warning(
                    "Snowflake session expired or ReauthenticationRequest detected during executemany (%s). "
                    "Resetting connection and retrying operation once...",
                    type(exc).__name__,
                )
                new_conn = self._conn_proxy._manager.reconnect()
                self._conn_proxy._real_conn = new_conn
                self._real_cursor = new_conn.cursor()
                return self._real_cursor.executemany(*args, **kwargs)
            raise

    def fetchone(self) -> Any:
        try:
            return self._real_cursor.fetchone()
        except Exception as exc:
            if is_session_expired_error(exc):
                logger.warning(
                    "Snowflake session expired during fetchone (%s). Resetting connection.",
                    type(exc).__name__,
                )
                self._conn_proxy._manager.reset()
            raise

    def fetchmany(self, size: Optional[int] = None) -> Any:
        try:
            return self._real_cursor.fetchmany(size) if size is not None else self._real_cursor.fetchmany()
        except Exception as exc:
            if is_session_expired_error(exc):
                logger.warning(
                    "Snowflake session expired during fetchmany (%s). Resetting connection.",
                    type(exc).__name__,
                )
                self._conn_proxy._manager.reset()
            raise

    def fetchall(self) -> Any:
        try:
            return self._real_cursor.fetchall()
        except Exception as exc:
            if is_session_expired_error(exc):
                logger.warning(
                    "Snowflake session expired during fetchall (%s). Resetting connection.",
                    type(exc).__name__,
                )
                self._conn_proxy._manager.reset()
            raise

    def close(self) -> None:
        try:
            self._real_cursor.close()
        except Exception:
            pass

    def __iter__(self) -> Any:
        return iter(self._real_cursor)

    def __next__(self) -> Any:
        return next(self._real_cursor)

    def __enter__(self) -> _PooledCursorProxy:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
        self.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real_cursor, name)


class _PooledConnectionProxy:
    """Lightweight connection proxy that keeps the physical Snowflake connection alive across queries."""

    def __init__(self, real_conn: Any, manager: SnowflakeConnectionManager) -> None:
        self._real_conn = real_conn
        self._manager = manager

    def cursor(self, *args: Any, **kwargs: Any) -> Any:
        try:
            cur = self._real_conn.cursor(*args, **kwargs)
            return _PooledCursorProxy(cur, self)
        except Exception as exc:
            if is_session_expired_error(exc):
                logger.warning(
                    "Snowflake session expired while creating cursor (%s). "
                    "Resetting connection and recreating cursor once...",
                    type(exc).__name__,
                )
                self._real_conn = self._manager.reconnect()
                cur = self._real_conn.cursor(*args, **kwargs)
                return _PooledCursorProxy(cur, self)
            raise

    def commit(self) -> None:
        try:
            self._real_conn.commit()
        except Exception as exc:
            if is_session_expired_error(exc):
                logger.warning(
                    "Snowflake session expired during commit (%s). Resetting connection.",
                    type(exc).__name__,
                )
                self._manager.reset()
            raise

    def rollback(self) -> None:
        try:
            self._real_conn.rollback()
        except Exception as exc:
            if is_session_expired_error(exc):
                logger.warning(
                    "Snowflake session expired during rollback (%s). Resetting connection.",
                    type(exc).__name__,
                )
                self._manager.reset()
            raise

    def reset(self) -> None:
        """Reset underlying connection manager and discard this cached connection."""
        self._manager.reset()

    def close(self) -> None:
        # Prevent premature socket termination across queries
        pass

    def __enter__(self) -> _PooledConnectionProxy:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
        self.close()

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

        if getattr(self.config, "client_session_keep_alive", True):
            params["client_session_keep_alive"] = True

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
                    if getattr(self._connection, "expired", False):
                        logger.warning("Cached Snowflake connection marked expired. Discarding stale connection.")
                        self._connection = None
                    else:
                        is_closed_fn = getattr(self._connection, "is_closed", None)
                        if is_closed_fn and is_closed_fn():
                            logger.info("Cached Snowflake connection is closed. Discarding stale connection.")
                            self._connection = None
                        else:
                            return _PooledConnectionProxy(self._connection, self)
                except Exception:
                    self._connection = None

            self._connection = self._create_new_connection(bootstrap=False)
            return _PooledConnectionProxy(self._connection, self)

    def reset(self) -> None:
        """Explicitly reset and terminate cached connection to force recreation on next use.

        Follows Streamlit's connection reset semantics for stale/expired sessions.
        """
        self.close()
        logger.info("Snowflake connection cache reset.")

    def reconnect(self, bootstrap: bool = False) -> Any:
        """Force recreate the underlying physical connection, safely closing the stale one."""
        with self._lock:
            if self._connection is not None:
                try:
                    self._connection.close()
                except Exception:
                    pass
                self._connection = None
            self._connection = self._create_new_connection(bootstrap=bootstrap)
            self._last_successful_query = datetime.now(timezone.utc)
            logger.info("Snowflake physical connection successfully reconnected.")
            return self._connection

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


__all__ = [
    "SnowflakeConnectionManager",
    "SnowflakeHealthStatus",
    "SnowflakeSessionVerification",
    "is_session_expired_error",
    "_PooledConnectionProxy",
    "_PooledCursorProxy",
]

