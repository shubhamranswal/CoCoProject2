"""Tests for CoCo Reliability Agent integration, tool boundary, and grounding validation."""

import pytest
from datetime import datetime, timezone
from domain.enums import AlertStatus, FailureMode, Severity, TriggerType
from domain.exceptions import ValidationError
from domain.models import Alert, MLFailurePrediction
from repositories.memory.memory_repository import InMemoryRepository
from agents.reliability.coco_agent import CoCoReliabilityAgent


@pytest.fixture
def memory_repo_with_m204():
    repo = InMemoryRepository()
    from data.scenarios.m204_scenario import M204ScenarioEngine, ScenarioPhase
    from ml.features.feature_extractor import FeatureExtractor
    engine = M204ScenarioEngine("M204")
    meas = engine.generate_timeseries(phase=ScenarioPhase.ANOMALOUS, num_points=6)
    repo.save_measurements(meas)
    fv = FeatureExtractor().extract_features("M204", meas)
    repo.save_feature(fv)
    return repo


def test_coco_agent_investigate_critical_alert(memory_repo_with_m204):
    repo = memory_repo_with_m204
    agent = CoCoReliabilityAgent(repo)

    alert = Alert(
        alert_id="ALT-TEST-001",
        machine_id="M204",
        component_id="M204-BEARING-DE",
        severity=Severity.HIGH,
        status=AlertStatus.OPEN,
        trigger_reason="High vibration RMS breach",
        risk_score=78.5,
        failure_mode=FailureMode.BEARING_DEGRADATION,
    )
    repo.create_alert(alert)

    result = agent.investigate_alert(alert)
    assert result.investigation is not None
    assert len(result.evidence) > 0
    assert result.finding is not None
    assert result.recommendation is not None
    assert result.action_proposal is not None
    # Action proposal must require approval
    assert result.approval is not None
    assert result.approval.status.value == "PENDING"
    # No work order should exist yet before human approval
    work_orders = repo.list_work_orders(machine_id="M204")
    assert len(work_orders) == 0


def test_coco_agent_investigate_predictive_failure(memory_repo_with_m204):
    repo = memory_repo_with_m204
    agent = CoCoReliabilityAgent(repo)

    pred = MLFailurePrediction(
        prediction_id="PRED-M204-001",
        machine_id="M204",
        component_id="M204-BEARING-DE",
        failure_mode=FailureMode.BEARING_DEGRADATION,
        failure_probability=0.84,
        prediction_horizon_hours=24,
        model_name="BearingFailure-v1.0",
        model_version="1.0.0",
        training_dataset_version="v2026.03",
        feature_schema_version="v1.0",
        threshold_exceeded=True,
    )
    repo.save_prediction(pred)

    result = agent.investigate_prediction(pred)
    assert result.investigation.machine_id == "M204"
    assert len(result.evidence) > 0
    assert result.finding is not None
    assert result.action_proposal is not None
    assert result.approval is not None


def test_coco_agent_rejects_fabricated_machine_id(memory_repo_with_m204):
    repo = memory_repo_with_m204
    agent = CoCoReliabilityAgent(repo)

    fake_pred = MLFailurePrediction(
        prediction_id="PRED-FAKE-001",
        machine_id="GHOST_MACHINE_999",
        component_id="GHOST_BEARING",
        failure_mode=FailureMode.BEARING_DEGRADATION,
        failure_probability=0.88,
        prediction_horizon_hours=24,
        model_name="BearingFailure-v1.0",
        model_version="1.0.0",
        training_dataset_version="v2026.03",
        feature_schema_version="v1.0",
        threshold_exceeded=True,
    )

    with pytest.raises(ValidationError, match="Fabricated machine ID rejected"):
        agent.investigate_prediction(fake_pred)
