"""Regression tests for Milestone M6.5.4 Semantic Evidence Remediation.

Validates the four semantic remediation requirements:
1. Coolant Flow Semantics: S-M21-FLW (C-M21-CLT, 34.72 L/min) is not an exceedance
   and is not cited as causing bearing degradation.
2. Historical Failure Scope: Distinguish 3,212 total downtime events vs 7 machine
   breakdowns vs 3 component-specific bearing breakdown work orders (WO-000523, WO-000527, WO-000532, BD-BRG).
3. Production Order Scope: PRD-01280 belongs to M22 and is strictly excluded from M21;
   only PRD-01278 (211 units remaining, ₹83,134 exposure on M21) enters M21 evidence.
4. Recommendation Intent: Title "Inspect Drive-End Bearing Assembly", Action Type
   INSPECT_BEARING_ASSEMBLY, Status ADVISORY. Replacement considered only if inspection
   confirms defect; zero procurement claims.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest

from domain.enums import FailureMode, Priority, SensorType
from domain.models import (
    Evidence,
    Sensor,
    WorkOrder,
)
from domain.models.telemetry import TelemetryMeasurement
from tools.read.sensor_tools import GetSensorContextTool
from tools.read.maintenance_tools import GetHistoricalFailuresTool
from tools.read.supply_chain_tools import GetProductionContextTool
from agents.reliability.coco_adapter import (
    InvestigationContext,
    DeterministicCoCoAdapter,
    LiveCortexCoCoAdapter,
)


# ==============================================================================
# 1. Coolant Flow Semantics Tests
# ==============================================================================

def test_coolant_flow_threshold_and_non_exceedance():
    """Verify S-M21-FLW with 34.72 L/min is within normal limits and not marked as exceedance."""
    mock_repo = MagicMock()
    # warn=22.0, crit=15.0 -> lower bound threshold where val > warn is normal
    sensor_flw = Sensor(
        sensor_id="S-M21-FLW",
        machine_id="M21",
        component_id="C-M21-CLT",
        sensor_type=SensorType.FLOW,
        name="Coolant Flow",
        unit="L/min",
        range_min=0.0,
        range_max=100.0,
        warn_threshold=22.0,
        crit_threshold=15.0,
    )
    sensor_vib = Sensor(
        sensor_id="S-M21-VIB",
        machine_id="M21",
        component_id="C-M21-BRG",
        sensor_type=SensorType.VIBRATION,
        name="Vibration RMS",
        unit="mm/s",
        range_min=0.0,
        range_max=20.0,
        warn_threshold=2.8,
        crit_threshold=4.5,
    )
    mock_repo.get_sensors.return_value = [sensor_flw, sensor_vib]
    def _mock_get_recent_measurements(machine_id, sensor_id=None, **kwargs):
        if sensor_id == "S-M21-FLW":
            return [
                TelemetryMeasurement(
                    measurement_id="T1",
                    machine_id="M21",
                    sensor_id="S-M21-FLW",
                    timestamp=datetime.now(timezone.utc),
                    value=34.72,
                    unit="L/min",
                )
            ]
        elif sensor_id == "S-M21-VIB":
            return [
                TelemetryMeasurement(
                    measurement_id="T2",
                    machine_id="M21",
                    sensor_id="S-M21-VIB",
                    timestamp=datetime.now(timezone.utc),
                    value=4.836,
                    unit="mm/s",
                )
            ]
        return []
    mock_repo.get_recent_measurements.side_effect = _mock_get_recent_measurements

    tool = GetSensorContextTool(mock_repo)
    result = tool.execute("ADHOC", machine_id="M21")

    # Locate S-M21-FLW
    flw_item = next(s for s in result.sensors if s.sensor_id == "S-M21-FLW")
    assert flw_item.component_id == "C-M21-CLT"
    assert flw_item.latest_value == 34.72
    assert not flw_item.is_warning_exceeded, "34.72 L/min must NOT exceed lower-bound warning threshold 22.0"
    assert not flw_item.is_critical_exceeded

    # Locate S-M21-VIB (must be exceeded)
    vib_item = next(s for s in result.sensors if s.sensor_id == "S-M21-VIB")
    assert vib_item.component_id == "C-M21-BRG"
    assert vib_item.is_warning_exceeded
    assert vib_item.is_critical_exceeded


# ==============================================================================
# 2. Historical Failure Scope Tests
# ==============================================================================

def test_historical_failures_scope_separation():
    """Verify tool distinguishes 3 component bearing breakdowns, 7 machine breakdowns, and 3212 downtime events."""
    mock_repo = MagicMock()
    mock_repo.get_downtime_event_count.return_value = 3212

    # 3 bearing work orders on C-M21-BRG
    wo_brg1 = WorkOrder(
        work_order_id="WO-000523",
        machine_id="M21",
        component_id="C-M21-BRG",
        title="corrective",
        description="breakdown",
        failure_mode=FailureMode.BEARING_DEGRADATION,
        failure_code="BD-BRG",
        priority=Priority.HIGH,
    )
    wo_brg2 = WorkOrder(
        work_order_id="WO-000527",
        machine_id="M21",
        component_id="C-M21-BRG",
        title="corrective",
        description="breakdown",
        failure_mode=FailureMode.BEARING_DEGRADATION,
        failure_code="BD-BRG",
        priority=Priority.HIGH,
    )
    wo_brg3 = WorkOrder(
        work_order_id="WO-000532",
        machine_id="M21",
        component_id="C-M21-BRG",
        title="corrective",
        description="breakdown",
        failure_mode=FailureMode.BEARING_DEGRADATION,
        failure_code="BD-BRG",
        priority=Priority.HIGH,
    )
    # 1 tooling breakdown on C-M21-TLG
    wo_tlg = WorkOrder(
        work_order_id="WO-000537",
        machine_id="M21",
        component_id="C-M21-TLG",
        title="corrective",
        description="breakdown",
        failure_mode=FailureMode.MECHANICAL_WEAR,
        failure_code="BD-TLG",
        priority=Priority.HIGH,
    )
    mock_repo.list_work_orders.return_value = [wo_brg1, wo_brg2, wo_brg3, wo_tlg]

    # 7 total machine breakdowns
    mock_repo.get_failure_history.return_value = [
        MagicMock(component_id="C-M21-BRG", failure_mode=FailureMode.BEARING_DEGRADATION),
        MagicMock(component_id="C-M21-BRG", failure_mode=FailureMode.BEARING_DEGRADATION),
        MagicMock(component_id="C-M21-BRG", failure_mode=FailureMode.BEARING_DEGRADATION),
        MagicMock(component_id="C-M21-TLG", failure_mode=FailureMode.MECHANICAL_WEAR),
        MagicMock(component_id="C-M21-ELC", failure_mode=FailureMode.UNPLANNED_DOWNTIME),
        MagicMock(component_id="C-M21-MTR", failure_mode=FailureMode.MOTOR_OVERHEATING),
        MagicMock(component_id="C-M21-DRV", failure_mode=FailureMode.MECHANICAL_WEAR),
    ]

    tool = GetHistoricalFailuresTool(mock_repo)
    res = tool.execute(
        "ADHOC",
        machine_id="M21",
        component_id="C-M21-BRG",
        failure_code="BD-BRG",
    )

    assert res.scope == "COMPONENT_SPECIFIC"
    assert res.failure_count == 3
    assert res.machine_breakdown_count == 7
    assert res.total_downtime_events == 3212
    assert sorted(res.historical_work_orders) == ["WO-000523", "WO-000527", "WO-000532"]


# ==============================================================================
# 3. Production Order Scope Tests
# ==============================================================================

def test_production_order_machine_filtering():
    """Verify PRD-01280 (M22) is strictly excluded and PRD-01278 (M21) is included with correct exposure."""
    mock_repo = MagicMock()
    order_m21 = MagicMock()
    order_m21.production_order_id = "PRD-01278"
    order_m21.machine_id = "M21"
    order_m21.product_id = "P008"
    order_m21.planned_qty = 3894
    order_m21.produced_qty = 3683
    order_m21.status = "in_progress"
    order_m21.priority = "Medium"

    order_m22 = MagicMock()
    order_m22.production_order_id = "PRD-01280"
    order_m22.machine_id = "M22"
    order_m22.product_id = "P001"
    order_m22.planned_qty = 2000
    order_m22.produced_qty = 2000
    order_m22.status = "completed"
    order_m22.priority = "Medium"

    mock_repo.list_production_orders.return_value = [order_m21, order_m22]

    tool = GetProductionContextTool(mock_repo)
    res = tool.execute("ADHOC", machine_id="M21")

    assert res.active_order_count == 1
    assert len(res.orders) == 1
    o = res.orders[0]
    assert o.order_id == "PRD-01278"
    assert o.machine_id == "M21"
    assert o.remaining_qty == 211
    assert o.unfulfilled_revenue_exposure_inr == 83134.0
    assert not any(ord_item.order_id == "PRD-01280" for ord_item in res.orders)


# ==============================================================================
# 4. Recommendation Semantic Alignment Tests
# ==============================================================================

def test_recommendation_alignment_deterministic_adapter():
    """Verify DeterministicCoCoAdapter aligns recommendation title, action_type, and status."""
    adapter = DeterministicCoCoAdapter()
    context = InvestigationContext(
        investigation_id="INV-M21-001",
        machine_id="M21",
        evidence_items=[
            Evidence(
                evidence_id="EV-VIB-01",
                investigation_id="INV-M21-001",
                evidence_type="TELEMETRY",
                category="SENSOR",
                source="sensor",
                metric="vibration_rms",
                observed_value=4.836,
                relationship="SUPPORTS",
                machine_id="M21",
                component_id="C-M21-BRG",
            )
        ],
    )

    res = adapter.reason(context)
    assert len(res.recommendations) >= 1
    rec = res.recommendations[0]

    assert rec.title == "Inspect Drive-End Bearing Assembly"
    assert rec.action_type == "INSPECT_BEARING_ASSEMBLY"
    assert rec.status == "ADVISORY"
    assert "replacement should be considered only if" in rec.suggested_next_step.lower()
    assert "expedite po" not in rec.suggested_next_step.lower()

    # Verify hypotheses do not cite coolant flow
    for h in res.hypotheses:
        assert "flow" not in h.statement.lower()
        assert "coolant" not in h.statement.lower()


def test_recommendation_alignment_cortex_adapter_sanitization():
    """Verify LiveCortexCoCoAdapter sanitizes LLM output to enforce action_type and advisory title."""
    adapter = LiveCortexCoCoAdapter(connection_mgr=MagicMock())
    context = InvestigationContext(
        investigation_id="INV-001",
        machine_id="M21",
        evidence_items=[
            Evidence(
                evidence_id="EV-01",
                investigation_id="INV-001",
                evidence_type="TELEMETRY",
                category="SENSOR",
                source="sensor",
                metric="vibration_rms",
                observed_value=4.8,
                relationship="SUPPORTS",
                machine_id="M21",
                component_id="C-M21-BRG",
            )
        ],
    )

    raw_json = """
    {
      "summary": "Bearing issue detected.",
      "hypotheses": [
        {
          "hypothesis_id": "HYP-01",
          "hypothesis_name": "Bearing Issue",
          "statement": "Machine M21 is experiencing bearing degradation due to vibration and flow rate readings.",
          "failure_mode": "BEARING_DEGRADATION",
          "supporting_evidence_ids": ["EV-01"]
        }
      ],
      "findings": [
        {
          "finding_id": "FIND-01",
          "summary": "High vibration",
          "statement": "High vibration observed.",
          "evidence_refs": ["EV-01"]
        }
      ],
      "recommendations": [
        {
          "recommendation_id": "REC-01",
          "title": "Replace Bearing Immediately",
          "statement": "Order parts and replace bearing.",
          "action_type": "INSPECT_BEARING",
          "status": "APPROVED",
          "evidence_refs": ["EV-01"]
        }
      ],
      "limitations": ["Model output validated."]
    }
    """

    res = adapter._parse_and_validate_cortex_response(raw_json, context)
    assert res is not None

    # Verify hypothesis statement had flow rate stripped
    assert "flow rate" not in res.hypotheses[0].statement.lower()

    # Verify recommendation title and status are normalized
    rec = res.recommendations[0]
    assert rec.title == "Inspect Drive-End Bearing Assembly"
    assert rec.action_type == "INSPECT_BEARING_ASSEMBLY"
    assert rec.status == "ADVISORY"


# ==============================================================================
# 5. Provenance Evidence Count Semantics Tests
# ==============================================================================

def test_provenance_evidence_count_semantics():
    """Verify evidence_count in provenance strictly matches total investigation evidence."""
    from repositories.memory.memory_repository import InMemoryRepository
    from services.investigation_service import InvestigationService
    from tools.registry import create_m4_tool_registry
    from domain.models.intelligence import InvestigationRequest, TriggerType

    mem_repo = InMemoryRepository(seed=True)
    tools = create_m4_tool_registry(mem_repo)
    service = InvestigationService(repository=mem_repo, tool_registry=tools)

    req = InvestigationRequest(
        request_id="REQ-EVID-TEST-01",
        investigation_id="INV-EVID-TEST-001",
        trigger_type=TriggerType.MACHINE,
        machine_id="M21",
    )

    res = service.investigate(req)
    assert res is not None

    persisted = mem_repo.get_investigation("INV-EVID-TEST-001")
    assert persisted is not None

    # Prove evidence_count equals total evidence records in repository
    persisted_evidence = mem_repo.get_evidence("INV-EVID-TEST-001")
    assert len(persisted_evidence) == persisted.provenance["evidence_count"]
    assert len(persisted_evidence) == len(persisted.evidence)


# ==============================================================================
# 6. Idempotent Replay & Snapshot Replacement Tests
# ==============================================================================

def test_idempotent_replay_snapshot_replacement():
    """Verify replaying same investigation ID eliminates stale child records and duplicates."""
    from repositories.memory.memory_repository import InMemoryRepository
    from services.investigation_service import InvestigationService
    from tools.registry import create_m4_tool_registry
    from domain.models.intelligence import InvestigationRequest, TriggerType

    mem_repo = InMemoryRepository(seed=True)
    tools = create_m4_tool_registry(mem_repo)
    service = InvestigationService(repository=mem_repo, tool_registry=tools)

    req = InvestigationRequest(
        request_id="REQ-REPLAY-01",
        investigation_id="INV-REPLAY-001",
        trigger_type=TriggerType.MACHINE,
        machine_id="M21",
        force_refresh=True,
    )

    # Initial Run
    res1 = service.investigate(req)
    assert res1 is not None

    inv1 = mem_repo.get_investigation("INV-REPLAY-001")
    initial_ev_count = len(inv1.evidence)
    initial_hyp_count = len(inv1.hypotheses)
    initial_fnd_count = len(inv1.findings)
    initial_rec_count = len(inv1.recommendations)

    assert initial_ev_count > 0
    assert initial_hyp_count == 1
    assert initial_rec_count == 1

    # Second Run (Replay with force_refresh)
    req.request_id = "REQ-REPLAY-02"
    res2 = service.investigate(req)
    assert res2 is not None

    inv2 = mem_repo.get_investigation("INV-REPLAY-001")

    # Prove snapshot replacement: no duplicated semantic records
    assert len(inv2.evidence) == initial_ev_count, "Evidence count must not double on replay"
    assert len(inv2.hypotheses) == initial_hyp_count, "Hypotheses count must not double on replay"
    assert len(inv2.findings) == initial_fnd_count, "Findings count must not double on replay"
    assert len(inv2.recommendations) == initial_rec_count, "Recommendations count must not double on replay"

    # All evidence references in findings must point to valid evidence in the current bundle
    valid_ev_ids = {e.evidence_id for e in inv2.evidence}
    for f in inv2.findings:
        for ref in f.evidence_refs:
            assert ref in valid_ev_ids, f"Finding ref {ref} must exist in current evidence snapshot"

    # Provenance remains truthful
    assert inv2.provenance["evidence_count"] == len(inv2.evidence)

