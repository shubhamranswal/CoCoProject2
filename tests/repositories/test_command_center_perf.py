"""Performance and scaling regression tests for the DeRule Command Center data path.

Follows Section 20 & 27 of DeRule performance specifications:
- Query-count scaling test across 5, 10, 20, 25 machines proving O(1) query complexity
- Verification of batch APIs (predictions, failure risks, features)
- No per-machine iterative loops
- No duplicate repository calls in the Command Center render path
- Snapshot consistency and cache invalidation contracts
"""

from __future__ import annotations

from datetime import datetime, timezone, date
from typing import Any, Dict, List
from unittest.mock import MagicMock, call

import pytest

from domain.enums import (
    AlertStatus,
    FailureMode,
    HealthStatus,
    MachineState,
    Severity,
    WorkOrderStatus,
)
from domain.models import (
    Alert,
    FailureRisk,
    FeatureVector,
    Machine,
    MachineOEEDaily,
    MLFailurePrediction,
    WorkOrder,
    Investigation,
)
from app.streamlit.services.view_service import (
    CommandCenterFacade,
    CommandCenterSnapshot,
)
from repositories.memory.memory_repository import InMemoryRepository
from repositories.snowflake.snowflake_repository import SnowflakeRepository


def _make_mock_fleet(count: int) -> List[Machine]:
    """Generate a fleet of N machines."""
    return [
        Machine(
            machine_id=f"M{i:02d}",
            line_id=f"L{(i % 3) + 1}",
            machine_code=f"M{i:02d}",
            name=f"Press {i:02d}",
            asset_type="PRESS",
            model="XP-200",
            criticality="CRITICAL" if i % 2 == 0 else "MEDIUM",
            health_status=HealthStatus.CRITICAL if i == 1 else HealthStatus.HEALTHY,
            state=MachineState.RUNNING,
        )
        for i in range(1, count + 1)
    ]


@pytest.mark.parametrize("machine_count", [5, 10, 20, 25])
def test_command_center_query_scaling_is_o1(machine_count: int):
    """Assert query count does NOT scale with machine count (O(1) complexity)."""
    mock_repo = MagicMock()
    fleet = _make_mock_fleet(machine_count)
    mock_repo.list_machines.return_value = fleet

    # Mock batch failure risks
    mock_repo.get_latest_failure_risks.return_value = {
        m.machine_id: FailureRisk(
            risk_id=f"R-{m.machine_id}",
            machine_id=m.machine_id,
            failure_mode=FailureMode.BEARING_DEGRADATION,
            risk_score=0.25,
            prediction_horizon_hours=168,
            model_version="1.0.0",
            prediction_timestamp="2026-10-02",
            confidence=0.9,
        )
        for m in fleet
    }

    # Mock open alerts
    mock_repo.list_alerts.return_value = [
        Alert(
            alert_id="ALT-001",
            machine_id="M01",
            component_id="COMP-01",
            severity=Severity.CRITICAL,
            status=AlertStatus.OPEN,
            trigger_reason="Bearing vibration threshold exceedance",
            risk_score=0.88,
        )
    ]

    mock_repo.list_work_orders.return_value = []
    mock_repo.list_investigations.return_value = []
    mock_repo.list_action_approvals.return_value = []
    mock_repo.get_latest_predictions.return_value = {}
    mock_repo.get_latest_features_batch.return_value = {}
    mock_repo.get_fleet_oee_summary.return_value = {
        "oee": 0.85,
        "availability": 0.92,
        "performance": 0.94,
        "quality": 0.98,
    }

    facade = CommandCenterFacade(repo=mock_repo)
    snapshot = facade.get_command_center_snapshot(force_refresh=True)

    assert len(snapshot.machines) == machine_count
    assert len(snapshot.asset_grid) == machine_count

    # Verify O(1) query calls: Exactly 1 call for each batch resource
    assert mock_repo.list_machines.call_count == 1
    assert mock_repo.list_alerts.call_count == 1
    assert mock_repo.list_work_orders.call_count == 1
    assert mock_repo.get_latest_failure_risks.call_count == 1
    assert mock_repo.list_investigations.call_count == 1

    # Verify per-machine individual queries are NEVER called
    assert mock_repo.get_machine.call_count == 0
    assert mock_repo.get_latest_failure_risk.call_count == 0
    assert mock_repo.get_latest_prediction.call_count == 0
    assert mock_repo.get_latest_features.call_count == 0


def test_command_center_zero_duplicate_queries_on_render_path():
    """Verify sequential presentation calls (kpis, critical_events, grid, investigations) use the cached snapshot."""
    mock_repo = MagicMock()
    fleet = _make_mock_fleet(10)
    mock_repo.list_machines.return_value = fleet
    mock_repo.list_alerts.return_value = []
    mock_repo.list_work_orders.return_value = []
    mock_repo.list_investigations.return_value = []
    mock_repo.get_latest_failure_risks.return_value = {}
    mock_repo.get_fleet_oee_summary.return_value = {
        "oee": 0.85,
        "availability": 0.92,
        "performance": 0.94,
        "quality": 0.98,
    }

    facade = CommandCenterFacade(repo=mock_repo)

    # 1. First call populates cache
    kpis = facade.get_kpis()
    assert kpis["total_machines"] == 10
    initial_machine_calls = mock_repo.list_machines.call_count
    assert initial_machine_calls == 1

    # 2. Subsequent calls within TTL should use cached snapshot with ZERO extra DB calls
    crit = facade.get_critical_events()
    assert crit == []
    assert mock_repo.list_machines.call_count == 1

    grid = facade.get_asset_grid()
    assert len(grid) == 10
    assert mock_repo.list_machines.call_count == 1

    invs = facade.get_investigations()
    assert invs == []
    assert mock_repo.list_investigations.call_count == 1


def test_command_center_snapshot_invalidation():
    """Verify invalidate_snapshot_cache causes subsequent calls to re-query repository."""
    mock_repo = MagicMock()
    mock_repo.list_machines.return_value = _make_mock_fleet(5)
    mock_repo.list_alerts.return_value = []
    mock_repo.list_work_orders.return_value = []
    mock_repo.list_investigations.return_value = []
    mock_repo.get_latest_failure_risks.return_value = {}

    facade = CommandCenterFacade(repo=mock_repo)
    facade.get_command_center_snapshot()
    assert mock_repo.list_machines.call_count == 1

    # Invalidate cache
    facade.invalidate_snapshot_cache()

    # Next call must re-query
    facade.get_command_center_snapshot()
    assert mock_repo.list_machines.call_count == 2


def test_memory_repo_fleet_oee_and_batch_features():
    """Verify InMemoryRepository implementations of get_fleet_oee_summary and get_latest_features_batch."""
    repo = InMemoryRepository()

    # Save a feature vector for M204
    feat = FeatureVector(
        feature_id="F1",
        machine_id="M204",
        timestamp=datetime.now(timezone.utc),
        window_minutes=1440,
        vibration_rms=0.75,
        vibration_peak=1.2,
        temperature_mean=65.0,
        temperature_slope=0.5,
        rpm_mean=1450.0,
        rpm_variance=2.0,
        current_mean=12.5,
    )
    repo.save_feature(feat)

    # Batch features test
    feats = repo.get_latest_features_batch(["M204", "NONEXISTENT"])
    assert "M204" in feats
    assert feats["M204"].vibration_rms == 0.75
    assert "NONEXISTENT" not in feats

    # Fleet OEE summary test
    oee_summary = repo.get_fleet_oee_summary()
    assert "oee" in oee_summary
    assert "availability" in oee_summary
    assert 0.0 <= oee_summary["oee"] <= 1.0


def test_snowflake_repo_batch_features_sql_contract():
    """Verify SnowflakeRepository.get_latest_features_batch constructs valid windowed parameterized query."""
    mock_conn_mgr = MagicMock()
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn_mgr.get_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cur

    # Mock single row return
    mock_cur.fetchall.return_value = [
        ("M01", date(2026, 9, 28), 1.67, 1.87, 51.5, 0.17, 1435.0, 21.1)
    ]

    repo = SnowflakeRepository(connection_manager=mock_conn_mgr)
    res = repo.get_latest_features_batch(["M01", "M02"])

    assert "M01" in res
    assert res["M01"].vibration_rms == 1.67
    assert mock_cur.execute.call_count == 1

    sql, params = mock_cur.execute.call_args[0]
    assert "WITH ranked AS" in sql
    assert "ROW_NUMBER() OVER (PARTITION BY machine_id ORDER BY feature_date DESC)" in sql
    assert "WHERE rn = 1" in sql
    assert params == ("M01", "M02")
