"""Tests for Snowflake connection configuration and safety."""

from config import SnowflakeConfig
from repositories.snowflake.connection import SnowflakeConnectionManager


def test_snowflake_unconfigured_status():
    cfg = SnowflakeConfig(account="", user="", password="")
    mgr = SnowflakeConnectionManager(cfg)
    assert not mgr.is_configured

    success, message = mgr.test_connection()
    assert not success
    assert "not configured" in message.lower()


def test_password_is_never_leaked_in_errors():
    secret_pass = "SuperSecretIndustrialPass123!"
    cfg = SnowflakeConfig(
        account="dummy-account",
        user="dummy-user",
        password=secret_pass,
        warehouse="COMPUTE_WH",
        database="DUMMY_DB",
        schema="DUMMY_SCHEMA",
    )
    mgr = SnowflakeConnectionManager(cfg)
    assert mgr.is_configured

    success, message = mgr.test_connection()
    assert not success
    # Crucial security check: The raw password must NOT appear anywhere in the output message
    assert secret_pass not in message
