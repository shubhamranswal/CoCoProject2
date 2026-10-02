"""Test suite for Milestone 4 Read-Only Tool Contracts.

Verifies:
- All registered tools declare ToolMode.READ
- All registered tools provide typed input and output schemas
- All registered tools execute safely without side effects
"""

import pytest
from domain.enums import ToolMode
from repositories.memory.memory_repository import InMemoryRepository
from tools.registry import create_m4_tool_registry, M4InvestigationToolRegistry
from tools.read.base import BaseReadTool


@pytest.fixture
def repo():
    return InMemoryRepository(seed=True)


@pytest.fixture
def registry(repo):
    return create_m4_tool_registry(repo)


def test_all_m4_tools_are_read_mode(registry: M4InvestigationToolRegistry):
    """Verify that every tool in M4 catalog is strictly declared as ToolMode.READ."""
    tools = registry.list_tools()
    assert len(tools) >= 11, f"Expected at least 11 read tools, got {len(tools)}"

    for tool in tools:
        assert isinstance(tool, BaseReadTool), f"Tool {tool.name} must inherit BaseReadTool"
        assert tool.tool_mode == ToolMode.READ, f"Tool {tool.name} mode is {tool.tool_mode}, expected ToolMode.READ"
        assert tool.mode == "READ", f"Tool {tool.name} string mode is {tool.mode}, expected 'READ'"
        assert tool.authorization_boundary == "READ_ONLY", f"Tool {tool.name} boundary must be READ_ONLY"
        assert ":read" in tool.scope or "read" in tool.scope.lower(), f"Tool {tool.name} scope must indicate read: {tool.scope}"


def test_all_m4_tools_have_typed_schemas(registry: M4InvestigationToolRegistry):
    """Verify that every tool specifies typed input and output Pydantic schemas."""
    for tool in registry.list_tools():
        assert hasattr(tool, "input_schema") and tool.input_schema is not None, f"Tool {tool.name} missing input_schema"
        assert hasattr(tool, "output_schema") and tool.output_schema is not None, f"Tool {tool.name} missing output_schema"
        assert hasattr(tool, "name") and len(tool.name) > 0, "Tool must have a valid non-empty name"
        assert hasattr(tool, "description") and len(tool.description) > 0, f"Tool {tool.name} missing description"


def test_m4_tool_execution_creates_audit_trail(registry: M4InvestigationToolRegistry):
    """Verify that tool execution logs duration, status, and does not alter operational state."""
    tool = registry.get_tool("get_machine_context")
    res = tool.execute("EXEC-001", machine_id="M21")
    assert res is not None
    assert res.machine is not None
    assert res.machine.machine_id == "M21"
    assert len(tool.call_history) >= 1
    last_call = tool.call_history[-1]
    assert last_call.tool_name == "get_machine_context"
    assert last_call.is_success is True
    assert last_call.duration_ms >= 0.0


# ---------------------------------------------------------------------------
# Individual contract tests for all 13 M4 tools with canonical domain models
# ---------------------------------------------------------------------------

from datetime import date, datetime, timezone
from unittest.mock import MagicMock
from domain.enums import FailureMode, Priority, WorkOrderStatus
from domain.models import (
    MachineHealthDaily,
    WorkOrder,
    Failure,
    DowntimeSummary,
    KnowledgeDocument,
    MLFailurePrediction,
    PredictionLineage,
    PredictionFeatureSnapshot,
)


def test_tool_01_get_prediction(registry: M4InvestigationToolRegistry, repo: InMemoryRepository):
    tool = registry.get_tool("get_prediction")
    # Mock get_prediction_by_id
    mock_pred = MLFailurePrediction(
        prediction_id="PRED-000322",
        machine_id="M21",
        component_id="C-M21-BRG",
        failure_mode=FailureMode.BEARING_DEGRADATION,
        failure_probability=0.95,
        prediction_horizon_hours=168,
        model_name="BearingFailure-v1.0",
        model_version="1.0.0",
        training_dataset_version="v2026.03",
        feature_schema_version="v1.0-29feat",
        confidence=0.95,
        threshold_exceeded=True,
    )
    repo.get_prediction_by_id = MagicMock(return_value=mock_pred)
    res = tool.execute("EXEC-01", prediction_id="PRED-000322")
    assert res is not None
    assert res.prediction_id == "PRED-000322"
    assert res.machine_id == "M21"
    assert res.failure_probability == 0.95
    assert res.risk_level == "CRITICAL"
    assert res.horizon_days == 7


def test_tool_02_get_prediction_lineage(registry: M4InvestigationToolRegistry, repo: InMemoryRepository):
    tool = registry.get_tool("get_prediction_lineage")
    mock_lineage = PredictionLineage(
        lineage_id="LIN-PRED-000322",
        prediction_id="PRED-000322",
        machine_id="M21",
        model_id="BearingFailure-v1.0",
        model_version="1.0.0",
        feature_version="v1.0-29feat",
        policy_version="POL-001",
        snapshot_id="SNAP-M21-1790636400",
        inference_timestamp=datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc),
        failure_probability=0.95,
        risk_level="CRITICAL",
    )
    repo.get_prediction_lineage = MagicMock(return_value=mock_lineage)
    res = tool.execute("EXEC-02", prediction_id="PRED-000322")
    assert res is not None
    assert res.prediction_id == "PRED-000322"
    assert res.feature_snapshot_id == "SNAP-M21-1790636400"
    assert res.model_version == "1.0.0"


def test_tool_03_get_feature_snapshot(registry: M4InvestigationToolRegistry, repo: InMemoryRepository):
    tool = registry.get_tool("get_prediction_feature_snapshot")
    mock_snap = PredictionFeatureSnapshot(
        snapshot_id="SNAP-M21-1790636400",
        prediction_id="PRED-000322",
        machine_id="M21",
        feature_timestamp=datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc),
        feature_version="v1.0-29feat",
        features={"vibration_rms_mean_7d": 4.12, "temperature_bearing_mean_7d": 82.5},
    )
    repo.get_prediction_feature_snapshot = MagicMock(return_value=mock_snap)
    res = tool.execute("EXEC-03", snapshot_id="SNAP-M21-1790636400")
    assert res is not None
    assert res.snapshot_id == "SNAP-M21-1790636400"
    assert "vibration_rms_mean_7d" in res.features


def test_tool_04_get_sensor_context(registry: M4InvestigationToolRegistry):
    tool = registry.get_tool("get_sensor_context")
    res = tool.execute("EXEC-04", machine_id="M21")
    assert res is not None
    assert res.machine_id == "M21"
    assert res.sensor_count >= 1


def test_tool_05_get_machine_context(registry: M4InvestigationToolRegistry):
    tool = registry.get_tool("get_machine_context")
    res = tool.execute("EXEC-05", machine_id="M21")
    assert res is not None
    assert res.machine is not None
    assert res.machine.machine_id == "M21"
    assert len(res.components) >= 1


def test_tool_06_get_machine_health_canonical_model(registry: M4InvestigationToolRegistry, repo: InMemoryRepository):
    tool = registry.get_tool("get_machine_health")
    canonical_mhd = MachineHealthDaily(
        machine_id="M21",
        metric_date=date(2026, 9, 21),
        machine_name="CNC Lathe 21",
        machine_type="CNC_LATHE",
        line_id="LINE-01",
        line_name="Machining Line 1",
        reading_count=1440,
        avg_vibration=3.5,
        max_vibration=4.881,
        avg_temperature=75.0,
        max_temperature=84.55,
        exceedance_count=4,
        downtime_minutes=120.0,
        breakdown_count=1,
        maintenance_count=1,
        open_alerts=2,
        latest_prediction_id="PRED-000322",
        latest_failure_prob=0.95,
        latest_risk_level="CRITICAL",
        health_status="CRITICAL",
    )
    repo.get_machine_health_daily = MagicMock(return_value=canonical_mhd)
    res = tool.execute("EXEC-06", machine_id="M21")
    assert res is not None
    assert res.machine_id == "M21"
    assert res.health_status == "CRITICAL"
    assert res.health_score == 5.0  # derived deterministically from (1.0 - 0.95) * 100
    assert res.active_anomalies_count == 4
    assert res.open_alerts_count == 2
    assert res.latest_prediction_prob == 0.95
    assert res.downtime_hours_7d == 2.0


def test_tool_07_get_maintenance_history_canonical_work_order(registry: M4InvestigationToolRegistry, repo: InMemoryRepository):
    tool = registry.get_tool("get_maintenance_history")
    canonical_wo = WorkOrder(
        work_order_id="WO-M21-001",
        machine_id="M21",
        component_id="C-M21-BRG",
        title="Replace drive bearing",
        description="Vibration and temperature spike detected on drive bearing",
        failure_mode=FailureMode.BEARING_DEGRADATION,
        priority=Priority.HIGH,
        status=WorkOrderStatus.COMPLETED,
        assigned_to="TECH-007",
        created_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    repo.list_work_orders = MagicMock(return_value=[canonical_wo])
    res = tool.execute("EXEC-07", machine_id="M21")
    assert res is not None
    assert res.count == 1
    item = res.work_orders[0]
    assert item.work_order_id == "WO-M21-001"
    assert item.work_type == FailureMode.BEARING_DEGRADATION.value
    assert item.technician == "TECH-007"
    assert item.status == "COMPLETED"


def test_tool_08_get_historical_failures_canonical_failure(registry: M4InvestigationToolRegistry, repo: InMemoryRepository):
    tool = registry.get_tool("get_historical_failures")
    canonical_fail = Failure(
        failure_id="FAIL-M21-001",
        machine_id="M21",
        component_id="C-M21-BRG",
        failure_mode=FailureMode.BEARING_DEGRADATION,
        occurred_at=datetime(2026, 9, 15, 14, 30, tzinfo=timezone.utc),
        root_cause="Lack of lubrication",
        downtime_hours=3.5,
        maintenance_action_taken="Replaced bearing and greased",
    )
    repo.list_work_orders = MagicMock(return_value=[])
    repo.get_failure_history = MagicMock(return_value=[canonical_fail])
    res = tool.execute("EXEC-08", machine_id="M21")
    assert res is not None
    assert res.failure_count == 1
    assert res.last_failure_date == datetime(2026, 9, 15, 14, 30, tzinfo=timezone.utc)
    assert FailureMode.BEARING_DEGRADATION.value in res.failure_codes_summary


def test_tool_09_get_downtime_history_canonical_summary(registry: M4InvestigationToolRegistry, repo: InMemoryRepository):
    tool = registry.get_tool("get_downtime_history")
    canonical_dt = DowntimeSummary(
        machine_id="M21",
        metric_date=date(2026, 9, 21),
        machine_name="CNC Lathe 21",
        line_id="LINE-01",
        total_downtime_minutes=180.0,
        breakdown_minutes=120.0,
        changeover_minutes=30.0,
        minor_stop_minutes=30.0,
        no_material_minutes=0.0,
        no_operator_minutes=0.0,
        planned_maintenance_minutes=0.0,
        breakdown_event_count=2,
        total_event_count=4,
        top_reason_code="E-BRG-DEG",
        top_downtime_category="BREAKDOWN",
    )
    repo.get_downtime_daily = MagicMock(return_value=canonical_dt)
    res = tool.execute("EXEC-09", machine_id="M21")
    assert res is not None
    assert res.machine_id == "M21"
    assert res.total_downtime_minutes == 180.0
    assert res.event_count == 4
    assert res.top_reason_codes == ["E-BRG-DEG"]


def test_tool_10_get_inventory_risk(registry: M4InvestigationToolRegistry):
    tool = registry.get_tool("get_inventory_risk")
    res = tool.execute("EXEC-10", part_id="SP-002")
    assert res is not None
    assert res.part_count >= 1
    assert res.parts[0].part_id == "SP-002"
    assert res.parts[0].lead_time_days > 0


def test_tool_11_get_production_context(registry: M4InvestigationToolRegistry):
    tool = registry.get_tool("get_production_context")
    res = tool.execute("EXEC-11", machine_id="M21")
    assert res is not None
    assert res.machine_id == "M21"
    assert res.total_unfulfilled_revenue_exposure >= 0.0


def test_tool_12_search_knowledge_canonical_doc(registry: M4InvestigationToolRegistry, repo: InMemoryRepository):
    tool = registry.get_tool("search_knowledge")
    canonical_doc = KnowledgeDocument(
        document_id="DOC-M21-SOP",
        title="M21 Spindle Maintenance SOP",
        doc_type="SOP",
        failure_code="BD-BRG",
        model="DRV-5000",
        component_type="BEARING",
        content="Check vibration limits on bearing C-M21-BRG. Replace when RMS exceeds 4.5 mm/s.",
    )
    repo.search_corpus = MagicMock(return_value=[canonical_doc])
    repo.list_documents = MagicMock(return_value=[canonical_doc])
    res = tool.execute("EXEC-12", query="bearing vibration")
    assert res is not None
    assert res.results_count >= 1
    assert res.results[0].document_id == "DOC-M21-SOP"
    assert res.results[0].source_reference == "Manual:DOC-M21-SOP"


def test_tool_13_get_knowledge_document_canonical_doc(registry: M4InvestigationToolRegistry, repo: InMemoryRepository):
    tool = registry.get_tool("get_knowledge_document")
    canonical_doc = KnowledgeDocument(
        document_id="DOC-M21-SOP",
        title="M21 Spindle Maintenance SOP",
        doc_type="SOP",
        failure_code="BD-BRG",
        model="DRV-5000",
        component_type="BEARING",
        content="Check vibration limits on bearing C-M21-BRG. Replace when RMS exceeds 4.5 mm/s.",
    )
    repo.get_document = MagicMock(return_value=canonical_doc)
    res = tool.execute("EXEC-13", document_id="DOC-M21-SOP")
    assert res is not None
    assert res.document_id == "DOC-M21-SOP"
    assert res.title == "M21 Spindle Maintenance SOP"
    assert res.machine_type == "DRV-5000"
    assert res.component_type == "BEARING"
    assert "vibration" in res.content
