"""Integration tests for ReliabilityInvestigationAgent orchestrator."""

from datetime import datetime, timezone
import pytest

from domain.enums import AlertStatus, FailureMode, InvestigationStatus, Priority, Severity
from domain.models import Alert
from repositories.memory.memory_repository import InMemoryRepository
from agents.reliability.agent import ReliabilityInvestigationAgent


def test_investigation_orchestrator_complete_flow():
    repo = InMemoryRepository()
    agent = ReliabilityInvestigationAgent(repository=repo)

    # 1. Create an active Alert and seed telemetry in repository
    alert = Alert(
        alert_id="ALT-M204-TEST-01",
        machine_id="M204",
        severity=Severity.HIGH,
        trigger_reason="Vibration RMS elevated past warning threshold",
        risk_score=0.72,
        failure_mode=FailureMode.BEARING_DEGRADATION,
    )
    repo.create_alert(alert)

    from data.scenarios.m204_scenario import M204ScenarioEngine, ScenarioPhase
    from ml.features.feature_extractor import FeatureExtractor
    engine = M204ScenarioEngine("M204")
    meas = engine.generate_timeseries(phase=ScenarioPhase.ANOMALOUS, num_points=6)
    repo.save_measurements(meas)
    fv = FeatureExtractor().extract_features("M204", meas)
    repo.save_feature(fv)

    # 2. Execute Investigation
    res = agent.investigate_alert("ALT-M204-TEST-01")


    # 3. Assert Evidence Collection
    assert len(res.evidence) >= 7
    ev_types = {e.evidence_type for e in res.evidence}
    assert "TELEMETRY" in ev_types
    assert "FAILURE_HISTORY" in ev_types
    assert "MAINTENANCE" in ev_types
    assert "DOCUMENT" in ev_types
    assert "OEE" in ev_types

    # 4. Assert Hypotheses & Finding
    assert len(res.hypotheses) == 3
    assert res.finding.confidence >= 0.75
    assert len(res.finding.observed_facts) > 0
    assert len(res.finding.historical_facts) > 0
    assert len(res.finding.inferences) > 0

    # 5. Assert Recommendation & Action Proposal
    assert res.recommendation.action_type == "INSPECT_BEARING_ASSEMBLY"
    assert len(res.recommendation.suggested_checklist) > 0
    assert res.action_proposal.action_type == "INSPECT_BEARING_ASSEMBLY"
    assert res.action_proposal.requires_approval is True
    assert res.approval is not None
    assert res.approval.status.value == "PENDING"

    # 6. Assert Investigation Status
    assert res.investigation.status == InvestigationStatus.PENDING_APPROVAL

    # 7. Assert Audit Logging
    assert res.execution.status.value == "COMPLETED"
    assert len(res.execution.tool_calls) >= 5
