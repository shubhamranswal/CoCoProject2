"""Tests for Command Center query optimization and N+1 query elimination.

Verifies:
1. get_latest_failure_risks executes a single batched query using window function.
2. get_latest_predictions executes a single batched query using window function.
3. get_asset_grid avoids N+1 query loops across fleet machines.
"""

from unittest.mock import MagicMock
import pytest

from repositories.snowflake.snowflake_repository import SnowflakeRepository
from app.streamlit.services.view_service import CommandCenterFacade
from domain.models import Machine, FailureRisk, MLFailurePrediction
from domain.enums import HealthStatus, MachineState, FailureMode


def test_snowflake_repo_get_latest_failure_risks_single_query():
    """Verify get_latest_failure_risks executes exactly ONE SQL query with window partition."""
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        ("PRED-1", "M21", "BEARING_DEGRADATION", 0.95, 168, "XGB-v1", "2026-10-02T10:00:00", 0.95),
        ("PRED-2", "M22", "BEARING_DEGRADATION", 0.35, 168, "XGB-v1", "2026-10-02T10:00:00", 0.90),
    ]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_mgr = MagicMock()
    mock_mgr.get_connection.return_value = mock_conn

    repo = SnowflakeRepository(connection_manager=mock_mgr)
    risks = repo.get_latest_failure_risks(["M21", "M22"])

    assert mock_cursor.execute.call_count == 1
    query_sql = mock_cursor.execute.call_args[0][0]
    assert "PARTITION BY machine_id" in query_sql
    assert "rn = 1" in query_sql
    assert "M21" in risks
    assert "M22" in risks
    assert risks["M21"].risk_score == 0.95


def test_snowflake_repo_get_latest_predictions_single_query():
    """Verify get_latest_predictions executes exactly ONE SQL query with window partition."""
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        ("PRED-1", "2026-10-02T10:00:00", "M21", "C-M21-BRG", "XGB-v1", 7, 0.95, "HIGH", '{"vib": 0.45}'),
        ("PRED-2", "2026-10-02T10:00:00", "M22", "C-M22-MTR", "XGB-v1", 7, 0.40, "MEDIUM", '{"cur": 12.0}'),
    ]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_mgr = MagicMock()
    mock_mgr.get_connection.return_value = mock_conn

    repo = SnowflakeRepository(connection_manager=mock_mgr)
    preds = repo.get_latest_predictions(["M21", "M22"])

    assert mock_cursor.execute.call_count == 1
    query_sql = mock_cursor.execute.call_args[0][0]
    assert "PARTITION BY machine_id" in query_sql
    assert "rn = 1" in query_sql
    assert "M21" in preds
    assert "M22" in preds
    assert preds["M21"].failure_mode == FailureMode.BEARING_DEGRADATION
    assert preds["M22"].failure_mode == FailureMode.MOTOR_OVERHEATING


def test_get_asset_grid_avoids_n_plus_one_queries():
    """Verify get_asset_grid uses batched queries rather than O(N) queries per machine."""
    mock_repo = MagicMock()
    # Simulate a fleet of 10 machines
    mock_repo.list_machines.return_value = [
        Machine(
            machine_id=f"M{i}",
            line_id="LINE-01",
            machine_code=f"M{i}",
            name=f"Grinder {i}",
            asset_type="GRINDER",
            model="X500",
            criticality="CRITICAL",
            health_status=HealthStatus.HEALTHY,
            state=MachineState.RUNNING,
        )
        for i in range(10)
    ]
    mock_repo.get_latest_failure_risks.return_value = {
        f"M{i}": FailureRisk(
            risk_id=f"R{i}",
            machine_id=f"M{i}",
            failure_mode=FailureMode.BEARING_DEGRADATION,
            risk_score=0.15,
            prediction_horizon_hours=168,
            model_version="v1",
            prediction_timestamp="2026-10-02",
            confidence=0.9,
        )
        for i in range(10)
    }
    mock_repo.list_alerts.return_value = []

    facade = CommandCenterFacade(repo=mock_repo)
    grid = facade.get_asset_grid()

    assert len(grid) == 10
    # list_machines called once
    assert mock_repo.list_machines.call_count == 1
    # get_latest_failure_risks called once in batch, NOT 10 times in a loop!
    assert mock_repo.get_latest_failure_risks.call_count == 1
    # list_alerts called once in batch, NOT 10 times in a loop!
    assert mock_repo.list_alerts.call_count == 1
    # Individual per-machine queries MUST NOT be called in a loop
    assert mock_repo.get_latest_failure_risk.call_count == 0
    assert mock_repo.get_latest_features.call_count == 0
