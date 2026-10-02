"""Tests for Snowflake live integration path and static DDL validation.

Tests:
1. Static validation of all DDL files and order.
2. Health status reporting when unconfigured.
3. Live Snowflake path validation (skipped when credentials unavailable with exact message).
"""

from pathlib import Path
import pytest

from domain.enums import AlertStatus, HealthStatus, Severity
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


@pytest.mark.skipif(
    not SnowflakeConnectionManager().is_configured,
    reason="NOT EXECUTED: Snowflake credentials unavailable",
)
def test_snowflake_live_machine_contract_and_plant_id():
    """Verify live get_machine and list_machines correctly project plant_id."""
    mgr = SnowflakeConnectionManager()
    repo = SnowflakeRepository(mgr)

    # 1. get_machine("M21")
    m21 = repo.get_machine("M21")
    assert m21 is not None, "M21 must exist in live Snowflake"
    assert m21.machine_id == "M21"
    assert m21.plant_id == "PLT01", f"Expected plant_id='PLT01', got '{m21.plant_id}'"
    assert m21.line_id == "L5"

    # 2. list_machines()
    machines = repo.list_machines()
    assert len(machines) >= 20
    for m in machines:
        assert m.plant_id == "PLT01", f"Expected plant_id='PLT01' for machine {m.machine_id}, got '{m.plant_id}'"


@pytest.mark.skipif(
    not SnowflakeConnectionManager().is_configured,
    reason="NOT EXECUTED: Snowflake credentials unavailable",
)
def test_snowflake_live_health_assessment_m21():
    """Verify get_latest_health_assessment reads authoritative columns from ANALYTICS.MACHINE_HEALTH_DAILY."""
    mgr = SnowflakeConnectionManager()
    repo = SnowflakeRepository(mgr)

    assessment = repo.get_latest_health_assessment("M21")
    assert assessment is not None, "M21 health assessment must exist in ANALYTICS.MACHINE_HEALTH_DAILY"
    assert assessment.machine_id == "M21"
    assert assessment.health_status == HealthStatus.CRITICAL
    assert assessment.health_score <= 100.0
    assert assessment.updated_at is not None
    assert "Critical condition detected" in assessment.primary_concern


@pytest.mark.skipif(
    not SnowflakeConnectionManager().is_configured,
    reason="NOT EXECUTED: Snowflake credentials unavailable",
)
def test_snowflake_live_alert_deserialization():
    """Verify get_alert and list_alerts deserialize lowercase severity and status values cleanly."""
    mgr = SnowflakeConnectionManager()
    repo = SnowflakeRepository(mgr)

    # 1. get_alert for canonical ALT-000033
    alert = repo.get_alert("ALT-000033")
    assert alert is not None, "ALT-000033 must exist in CORE.ALERT"
    assert alert.alert_id == "ALT-000033"
    assert alert.machine_id == "M21"
    assert isinstance(alert.severity, Severity)
    assert isinstance(alert.status, AlertStatus)
    assert alert.severity == Severity.CRITICAL

    # 2. list_alerts for M21
    m21_alerts = repo.list_alerts(machine_id="M21")
    assert len(m21_alerts) > 0, "M21 must have alerts in CORE.ALERT"
    for a in m21_alerts:
        assert isinstance(a.severity, Severity)
        assert isinstance(a.status, AlertStatus)

    # 3. list_alerts with status filtering
    # In canonical dataset, M21's recent active alerts are in 'acknowledged' status -> AlertStatus.INVESTIGATING
    investigating_alerts = repo.list_alerts(machine_id="M21", status=AlertStatus.INVESTIGATING)
    assert len(investigating_alerts) > 0, "M21 should have acknowledged/investigating alerts"
    for a in investigating_alerts:
        assert a.status == AlertStatus.INVESTIGATING

    # Factory-wide open alerts exist
    open_alerts = repo.list_alerts(status=AlertStatus.OPEN)
    assert len(open_alerts) > 0, "Factory should have open alerts"
    for a in open_alerts:
        assert a.status == AlertStatus.OPEN
