"""Tests for Milestone 6.1: Snowflake connection and configuration hardening.

Validates:
- Password and Key-Pair authentication configuration
- Key-Pair PEM loading and PKCS8 DER conversion (encrypted and unencrypted)
- Credential masking (password and private key passphrase never exposed)
- verify_connection structured session inspection and diagnostics
- Environment defaults alignment
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from config import SnowflakeConfig, get_config
from repositories.snowflake.connection import (
    SnowflakeConnectionManager,
    SnowflakeHealthStatus,
    SnowflakeSessionVerification,
)


def _generate_test_rsa_pem(passphrase: str = None) -> bytes:
    """Helper to generate a real ephemeral RSA PEM private key for testing."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    if passphrase:
        encryption = serialization.BestAvailableEncryption(passphrase.encode("utf-8"))
    else:
        encryption = serialization.NoEncryption()

    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=encryption,
    )


def test_password_auth_configuration():
    cfg = SnowflakeConfig(
        account="xy12345.us-east-1",
        user="RELIABILITY_BOT",
        password="TopSecretPassword123!",
        warehouse="COMPUTE_WH",
        database="COCO_FACTORY",
        schema="CORE",
    )
    mgr = SnowflakeConnectionManager(cfg)
    assert mgr.is_configured
    assert cfg.auth_method == "password"


def test_key_pair_auth_configuration():
    cfg = SnowflakeConfig(
        account="xy12345.us-east-1",
        user="RELIABILITY_BOT",
        private_key_path="/path/to/rsa_key.p8",
        warehouse="COMPUTE_WH",
        database="COCO_FACTORY",
        schema="CORE",
    )
    mgr = SnowflakeConnectionManager(cfg)
    assert mgr.is_configured
    assert cfg.auth_method == "key_pair"


def test_unconfigured_states():
    # Missing user/password/key
    cfg1 = SnowflakeConfig(account="xy12345", user="", password="")
    assert not cfg1.is_configured
    assert cfg1.auth_method == "unconfigured"

    # Missing account
    cfg2 = SnowflakeConfig(account="", user="bot", password="pwd")
    assert not cfg2.is_configured

    # Missing both password and key_pair_path
    cfg3 = SnowflakeConfig(account="xy12345", user="bot", password="", private_key_path="")
    assert not cfg3.is_configured


def test_key_pair_pem_loading_unencrypted():
    pem_bytes = _generate_test_rsa_pem()
    with tempfile.NamedTemporaryFile(suffix=".p8", delete=False) as f:
        f.write(pem_bytes)
        temp_path = f.name

    try:
        cfg = SnowflakeConfig(
            account="test_acct",
            user="test_user",
            private_key_path=temp_path,
        )
        mgr = SnowflakeConnectionManager(cfg)
        der_bytes = mgr.load_private_key_bytes()
        assert isinstance(der_bytes, bytes)
        assert len(der_bytes) > 0
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_key_pair_pem_loading_with_passphrase():
    secret_passphrase = "SecretPassphrase999!"
    pem_bytes = _generate_test_rsa_pem(passphrase=secret_passphrase)
    with tempfile.NamedTemporaryFile(suffix=".p8", delete=False) as f:
        f.write(pem_bytes)
        temp_path = f.name

    try:
        cfg = SnowflakeConfig(
            account="test_acct",
            user="test_user",
            private_key_path=temp_path,
            private_key_passphrase=secret_passphrase,
        )
        mgr = SnowflakeConnectionManager(cfg)
        der_bytes = mgr.load_private_key_bytes()
        assert isinstance(der_bytes, bytes)
        assert len(der_bytes) > 0

        # Wrong passphrase test - ensures passphrase is not leaked in the exception
        cfg_bad = SnowflakeConfig(
            account="test_acct",
            user="test_user",
            private_key_path=temp_path,
            private_key_passphrase="WrongPassphrase!",
        )
        mgr_bad = SnowflakeConnectionManager(cfg_bad)
        with pytest.raises(ValueError) as excinfo:
            mgr_bad.load_private_key_bytes()
        assert "WrongPassphrase!" not in str(excinfo.value)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_missing_private_key_file():
    cfg = SnowflakeConfig(
        account="test_acct",
        user="test_user",
        private_key_path="non_existent_key_file.p8",
    )
    mgr = SnowflakeConnectionManager(cfg)
    with pytest.raises(FileNotFoundError):
        mgr.load_private_key_bytes()


def test_verify_connection_unconfigured():
    cfg = SnowflakeConfig(account="", user="", password="")
    mgr = SnowflakeConnectionManager(cfg)

    verification = mgr.verify_connection()
    assert isinstance(verification, SnowflakeSessionVerification)
    assert not verification.is_connected
    assert verification.auth_method == "unconfigured"
    assert "not configured" in verification.error_message.lower()


def test_verify_connection_with_mock_connector():
    mock_connector = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    # CURRENT_VERSION, CURRENT_USER, CURRENT_ROLE, CURRENT_WAREHOUSE, CURRENT_DATABASE, CURRENT_SCHEMA
    mock_cursor.fetchone.return_value = (
        "8.12.0",
        "RELIABILITY_BOT",
        "RELIABILITY_ENGINEER",
        "COMPUTE_WH",
        "COCO_FACTORY",
        "CORE",
    )
    mock_conn.cursor.return_value = mock_cursor
    mock_connector.connect.return_value = mock_conn

    cfg = SnowflakeConfig(
        account="test_acct",
        user="RELIABILITY_BOT",
        password="SecretPassword!",
        warehouse="COMPUTE_WH",
        database="COCO_FACTORY",
        schema="CORE",
        role="RELIABILITY_ENGINEER",
    )
    mgr = SnowflakeConnectionManager(cfg)

    mock_snowflake = MagicMock()
    mock_snowflake.connector = mock_connector
    with patch.dict(sys.modules, {"snowflake": mock_snowflake, "snowflake.connector": mock_connector}):
        verification = mgr.verify_connection()
        assert verification.is_connected
        assert verification.auth_method == "password"
        assert verification.version == "8.12.0"
        assert verification.user == "RELIABILITY_BOT"
        assert verification.role == "RELIABILITY_ENGINEER"
        assert verification.warehouse == "COMPUTE_WH"
        assert verification.database == "COCO_FACTORY"
        assert verification.schema == "CORE"
        assert verification.latency_ms is not None
        assert verification.error_message is None

        # Verify test_connection also succeeds
        success, msg = mgr.test_connection()
        assert success
        assert "password" in msg
        assert "8.12.0" in msg

        # Verify get_health_status reports CONNECTED
        health = mgr.get_health_status()
        assert health.connection == "CONNECTED"
        assert health.database == "8.12.0" or health.database == "COCO_FACTORY"


def test_credentials_never_leaked_in_verification_error():
    secret_pass = "UltraSecretPassword987!"
    secret_passphrase = "UltraSecretPassphrase654!"

    mock_connector = MagicMock()
    mock_connector.connect.side_effect = Exception(
        f"Authentication failed with password '{secret_pass}' and key '{secret_passphrase}'"
    )

    cfg = SnowflakeConfig(
        account="test_acct",
        user="test_user",
        password=secret_pass,
        private_key_passphrase=secret_passphrase,
    )
    mgr = SnowflakeConnectionManager(cfg)

    mock_snowflake = MagicMock()
    mock_snowflake.connector = mock_connector
    with patch.dict(sys.modules, {"snowflake": mock_snowflake, "snowflake.connector": mock_connector}):
        verification = mgr.verify_connection()
        assert not verification.is_connected
        assert secret_pass not in verification.error_message
        assert secret_passphrase not in verification.error_message
        assert "******" in verification.error_message


def test_env_example_contains_m6_canonical_defaults():
    env_example_path = Path(__file__).parents[2] / ".env.example"
    assert env_example_path.exists()
    content = env_example_path.read_text(encoding="utf-8")

    assert "SNOWFLAKE_DATABASE=COCO_FACTORY" in content
    assert "SNOWFLAKE_SCHEMA=CORE" in content
    assert "SNOWFLAKE_PRIVATE_KEY_PATH=" in content
    assert "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE=" in content
    assert "COCO_FACTORY_SOURCE_ROOT=" in content
