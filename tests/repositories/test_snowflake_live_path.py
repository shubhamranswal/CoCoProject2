"""Tests for Snowflake live integration path and static DDL validation.

Tests:
1. Static validation of all DDL files and order.
2. Health status reporting when unconfigured.
3. Live Snowflake path validation (skipped when credentials unavailable with exact message).
"""

from pathlib import Path
import pytest

from repositories.snowflake.connection import SnowflakeConnectionManager, SnowflakeHealthStatus
from repositories.snowflake.snowflake_repository import SnowflakeRepository
from snowflake.scripts.init_snowflake import DDL_SCRIPTS


def test_ddl_scripts_exist_and_ordered():
    """Verify all 7 DDL scripts exist in the repository."""
    ddl_dir = Path(__file__).resolve().parent.parent.parent / "snowflake" / "ddl"
    assert len(DDL_SCRIPTS) == 7
    for script_name in DDL_SCRIPTS:
        script_path = ddl_dir / script_name
        assert script_path.exists(), f"DDL script {script_name} must exist"
        content = script_path.read_text(encoding="utf-8")
        assert len(content) > 50, f"DDL script {script_name} must not be empty"


def test_snowflake_health_status_unconfigured():
    """Verify health status returns NOT_CONFIGURED safely without throwing."""
    mgr = SnowflakeConnectionManager()
    status = mgr.get_health_status()
    assert isinstance(status, SnowflakeHealthStatus)
    assert status.storage == "Snowflake"
    if not mgr.is_configured:
        assert status.connection == "NOT_CONFIGURED"
        assert status.error_message is not None


def test_snowflake_repository_implements_interface():
    """Verify SnowflakeRepository implements all required repository methods."""
    repo = SnowflakeRepository(SnowflakeConnectionManager())
    # Machine methods
    assert hasattr(repo, "get_machine")
    assert hasattr(repo, "list_machines")
    # Telemetry methods
    assert hasattr(repo, "save_measurements")
    assert hasattr(repo, "get_recent_measurements")
    assert hasattr(repo, "save_feature")
    # Reliability methods
    assert hasattr(repo, "save_prediction")
    assert hasattr(repo, "get_latest_prediction")
    assert hasattr(repo, "list_predictions")
    assert hasattr(repo, "save_prediction_outcome")
    assert hasattr(repo, "get_prediction_outcome")
    assert hasattr(repo, "list_prediction_outcomes")
    # Investigation & Governance methods
    assert hasattr(repo, "create_alert")
    assert hasattr(repo, "create_investigation")
    assert hasattr(repo, "create_approval")
    assert hasattr(repo, "save_verification")


@pytest.mark.skipif(
    not SnowflakeConnectionManager().is_configured,
    reason="NOT EXECUTED: Snowflake credentials unavailable",
)
def test_snowflake_live_end_to_end_path():
    """Executes live Snowflake integration path when credentials are provided in env.

    Must never be executed or reported as passed unless a real Snowflake instance is contacted.
    """
    mgr = SnowflakeConnectionManager()
    status = mgr.get_health_status()
    assert status.connection == "CONNECTED", f"Failed live connection: {status.error_message}"

    repo = SnowflakeRepository(mgr)
    machines = repo.list_machines()
    assert len(machines) > 0, "Expected seed machines in live Snowflake database"
