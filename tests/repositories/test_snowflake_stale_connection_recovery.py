"""Tests for Snowflake stale/expired connection recovery and self-healing strategy.

Validates:
1. client_session_keep_alive is configured in connect parameters.
2. is_session_expired_error detects ReauthenticationRequest, error codes, and session expiration messages.
3. _PooledCursorProxy intercepts ReauthenticationRequest, resets connection, and retries once.
4. No infinite retry loop when session cannot be recovered.
5. SnowflakeConnectionManager.reset() and reconnect() discard stale connections.
6. Expired or closed cached connections are discarded automatically.
7. Streamlit facade reset mechanism triggers connection recreation.
"""

import sys
from unittest.mock import MagicMock, patch
import pytest

from config import SnowflakeConfig
from repositories.snowflake.connection import (
    SnowflakeConnectionManager,
    _PooledConnectionProxy,
    _PooledCursorProxy,
    is_session_expired_error,
)


class MockReauthenticationRequest(Exception):
    """Mock exception matching snowflake.connector.network.ReauthenticationRequest."""
    def __init__(self, cause=None):
        super().__init__("ReauthenticationRequest: Master token expired")
        self.cause = cause


class MockProgrammingError(Exception):
    """Mock exception matching snowflake.connector.errors.ProgrammingError."""
    def __init__(self, msg="ProgrammingError", errno=None):
        super().__init__(msg)
        self.msg = msg
        self.errno = errno


def test_client_session_keep_alive_in_connect_params():
    """Verify client_session_keep_alive=True is included in connection parameters."""
    cfg = SnowflakeConfig(
        account="xy12345.us-east-1",
        user="TEST_USER",
        password="SafePassword123!",
        client_session_keep_alive=True,
    )
    mgr = SnowflakeConnectionManager(cfg)
    params = mgr._build_connect_params()
    assert "client_session_keep_alive" in params
    assert params["client_session_keep_alive"] is True


def test_is_session_expired_error_detection():
    """Verify is_session_expired_error accurately detects authentication/session errors."""
    # 1. Direct ReauthenticationRequest
    reauth_exc = MockReauthenticationRequest()
    assert is_session_expired_error(reauth_exc) is True

    # 2. ProgrammingError wrapping ReauthenticationRequest in cause
    wrapped_exc = MockProgrammingError("Session renew failed")
    wrapped_exc.cause = reauth_exc
    assert is_session_expired_error(wrapped_exc) is True

    # 3. Exception with ReauthenticationRequest in message
    msg_exc = MockProgrammingError("snowflake.connector.network.ReauthenticationRequest: renewal failed")
    assert is_session_expired_error(msg_exc) is True

    # 4. Expired session GS codes
    assert is_session_expired_error(MockProgrammingError("Renew failed", errno=252007)) is True
    assert is_session_expired_error(MockProgrammingError("Session expired", errno=390112)) is True
    assert is_session_expired_error(MockProgrammingError("Master token expired", errno=390114)) is True

    # 5. Session expired keywords
    assert is_session_expired_error(Exception("Your session has expired. Please login again.")) is True
    assert is_session_expired_error(Exception("Failed to renew session token.")) is True

    # 6. Unrelated errors must NOT be detected as session expired
    assert is_session_expired_error(MockProgrammingError("Table COCO_FACTORY.CORE.MACHINE not found", errno=2003)) is False
    assert is_session_expired_error(ValueError("Invalid argument")) is False
    assert is_session_expired_error(None) is False


def test_pooled_cursor_proxy_retries_once_on_reauthentication_request():
    """Verify _PooledCursorProxy intercepts ReauthenticationRequest, reconnects, and retries once."""
    mock_stale_conn = MagicMock()
    mock_stale_cur = MagicMock()
    # Stale cursor raises ReauthenticationRequest on execute
    mock_stale_cur.execute.side_effect = MockProgrammingError("ReauthenticationRequest: renew token failed", errno=252007)
    mock_stale_conn.cursor.return_value = mock_stale_cur

    mock_fresh_conn = MagicMock()
    mock_fresh_cur = MagicMock()
    mock_fresh_cur.execute.return_value = mock_fresh_cur
    mock_fresh_cur.fetchone.return_value = ("M204", "RMS_G", 0.42)
    mock_fresh_conn.cursor.return_value = mock_fresh_cur

    mock_mgr = MagicMock(spec=SnowflakeConnectionManager)
    mock_mgr.reconnect.return_value = mock_fresh_conn

    proxy_conn = _PooledConnectionProxy(mock_stale_conn, mock_mgr)
    proxy_cur = proxy_conn.cursor()

    # Execution should encounter stale session, reconnect via manager, and retry on fresh cursor
    res = proxy_cur.execute("SELECT machine_id, unit, value FROM SENSOR_READING WHERE machine_id = %s", ("M204",))
    assert mock_stale_cur.execute.call_count == 1
    assert mock_mgr.reconnect.call_count == 1
    assert mock_fresh_cur.execute.call_count == 1
    assert proxy_conn._real_conn == mock_fresh_conn

    # fetchone reads from the active fresh cursor
    row = proxy_cur.fetchone()
    assert row == ("M204", "RMS_G", 0.42)


def test_no_infinite_retry_loop_on_persistent_session_failure():
    """Verify that if the retry also fails with session error, it raises and does NOT loop indefinitely."""
    mock_stale_conn = MagicMock()
    mock_stale_cur = MagicMock()
    mock_stale_cur.execute.side_effect = MockProgrammingError("ReauthenticationRequest", errno=252007)
    mock_stale_conn.cursor.return_value = mock_stale_cur

    mock_fresh_conn = MagicMock()
    mock_fresh_cur = MagicMock()
    # Retry also fails
    mock_fresh_cur.execute.side_effect = MockProgrammingError("ReauthenticationRequest", errno=252007)
    mock_fresh_conn.cursor.return_value = mock_fresh_cur

    mock_mgr = MagicMock(spec=SnowflakeConnectionManager)
    mock_mgr.reconnect.return_value = mock_fresh_conn

    proxy_conn = _PooledConnectionProxy(mock_stale_conn, mock_mgr)
    proxy_cur = proxy_conn.cursor()

    with pytest.raises(MockProgrammingError):
        proxy_cur.execute("SELECT 1")

    # Must be called exactly twice: 1 initial attempt + 1 retry
    assert mock_stale_cur.execute.call_count == 1
    assert mock_mgr.reconnect.call_count == 1
    assert mock_fresh_cur.execute.call_count == 1


def test_connection_manager_reset_clears_cached_connection():
    """Verify SnowflakeConnectionManager.reset() closes connection and invalidates cache."""
    cfg = SnowflakeConfig(
        account="xy12345.us-east-1",
        user="TEST_USER",
        password="SafePassword123!",
    )
    mgr = SnowflakeConnectionManager(cfg)
    mock_conn = MagicMock()
    mock_conn.is_closed.return_value = False
    mgr._connection = mock_conn

    mgr.reset()
    assert mock_conn.close.called
    assert mgr._connection is None


def test_connection_manager_discards_expired_flag():
    """Verify get_connection() discards a cached connection that was marked expired by driver."""
    cfg = SnowflakeConfig(
        account="xy12345.us-east-1",
        user="TEST_USER",
        password="SafePassword123!",
    )
    mgr = SnowflakeConnectionManager(cfg)

    # Simulate connection marked expired by snowflake connector
    old_conn = MagicMock()
    old_conn.expired = True
    mgr._connection = old_conn

    new_conn = MagicMock()
    new_conn.expired = False
    new_conn.is_closed.return_value = False

    with patch.object(mgr, "_create_new_connection", return_value=new_conn) as mock_create:
        conn = mgr.get_connection()
        assert mock_create.called
        assert mgr._connection == new_conn


def test_facade_reset_connection_integration():
    """Verify CommandCenterFacade.reset_connection triggers repo connection reset."""
    from app.streamlit.services.view_service import CommandCenterFacade

    mock_repo = MagicMock()
    facade = CommandCenterFacade(backend_mode="in_memory", repo=mock_repo)
    facade.reset_connection()
    assert mock_repo.reset.called


def test_repository_query_self_heals_transparently():
    """Verify SnowflakeRepository.get_recent_measurements self-heals when encountering ReauthenticationRequest."""
    from datetime import datetime, timezone
    from repositories.snowflake.snowflake_repository import SnowflakeRepository

    cfg = SnowflakeConfig(
        account="xy12345.us-east-1",
        user="TEST_USER",
        password="SafePassword123!",
    )
    mgr = SnowflakeConnectionManager(cfg)

    # Stale connection raises ReauthenticationRequest
    stale_conn = MagicMock()
    stale_cur = MagicMock()
    stale_cur.execute.side_effect = MockProgrammingError("ReauthenticationRequest", errno=252007)
    stale_conn.cursor.return_value = stale_cur

    # Fresh connection succeeds
    fresh_conn = MagicMock()
    fresh_cur = MagicMock()
    now_ts = datetime.now(timezone.utc)
    fresh_cur.fetchall.return_value = [
        ("MSR-001", "VIB_DE_RMS", "M204", now_ts, 0.45, "GOOD")
    ]
    fresh_conn.cursor.return_value = fresh_cur

    call_count = 0

    def mock_create(bootstrap=False):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return stale_conn
        return fresh_conn

    with patch.object(mgr, "_create_new_connection", side_effect=mock_create):
        repo = SnowflakeRepository(connection_manager=mgr)
        measurements = repo.get_recent_measurements("M204", limit=1)

        assert len(measurements) == 1
        assert measurements[0].machine_id == "M204"
        assert measurements[0].value == 0.45
        assert call_count == 2, "Should create stale conn initially, then reconnect once"


def test_safe_logging_never_exposes_secrets(caplog):
    """Verify self-healing reconnection logging never exposes passwords, keys, or tokens."""
    import logging

    secret_pass = "UltraSecretPassword999!"
    cfg = SnowflakeConfig(
        account="xy12345.us-east-1",
        user="TEST_USER",
        password=secret_pass,
    )
    mgr = SnowflakeConnectionManager(cfg)

    mock_stale_conn = MagicMock()
    mock_stale_cur = MagicMock()
    mock_stale_cur.execute.side_effect = MockProgrammingError(
        f"ReauthenticationRequest with token secret={secret_pass}", errno=252007
    )
    mock_stale_conn.cursor.return_value = mock_stale_cur

    mock_fresh_conn = MagicMock()
    mock_fresh_cur = MagicMock()
    mock_fresh_conn.cursor.return_value = mock_fresh_cur
    mock_mgr = MagicMock(spec=SnowflakeConnectionManager)
    mock_mgr.reconnect.return_value = mock_fresh_conn

    proxy_conn = _PooledConnectionProxy(mock_stale_conn, mock_mgr)
    proxy_cur = proxy_conn.cursor()

    with caplog.at_level(logging.WARNING):
        proxy_cur.execute("SELECT 1")

    # Verify log messages were emitted but secrets were never leaked
    assert "Snowflake session expired or ReauthenticationRequest detected" in caplog.text
    assert secret_pass not in caplog.text
