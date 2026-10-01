"""Unit tests for M5 Closed-Loop Physical Verification and Action Outcome recording.

Validates:
- Missing telemetry produces INCONCLUSIVE verdict (never assumed success)
- Persisting high vibration / critical risk produces FAILED / VERIFICATION_FAILED
- Nominal post-maintenance telemetry produces VERIFIED
- Automatic generation of ActionOutcome record for closed-loop learning
"""

from datetime import datetime, timezone
import pytest

from domain.enums import (
    FailureMode,
    HealthStatus,
    InvestigationStatus,
    Priority,
    VerificationStatus,
    WorkOrderStatus,
)
from domain.models import (
    FailureRisk,
    FeatureVector,
    Investigation,
    WorkOrder,
    VerificationPolicy,
)
from repositories.memory.memory_repository import InMemoryRepository
from services.verification_service import VerificationService
from services.work_order_service import WorkOrderService


@pytest.fixture
def m5_verif_setup():
    repo = InMemoryRepository()
    wo_svc = WorkOrderService(repository=repo, governance_repo=repo)
    verif_svc = VerificationService(
        repository=repo,
        maintenance_repo=repo,
        investigation_repo=repo,
        machine_repo=repo,
    )

    inv = Investigation(
        investigation_id="INV-M5-001",
        machine_id="M21",
        status=InvestigationStatus.PENDING_APPROVAL,
    )
    repo.create_investigation(inv)

    wo = WorkOrder(
        work_order_id="WO-M5-001",
        machine_id="M21",
        component_id="C-M21-BRG",
        investigation_id=inv.investigation_id,
        title="Replace Bearing C-M21-BRG",
        description="Physical replacement",
        failure_mode=FailureMode.BEARING_DEGRADATION,
        priority=Priority.HIGH,
        status=WorkOrderStatus.APPROVED,
    )
    wo_svc.create_work_order(wo)

    # Complete the work order
    completed_wo, _ = wo_svc.complete_work_order(
        work_order_id=wo.work_order_id,
        technician_name="tech.marcus",
        duration_hours=2.5,
        notes="Replaced bearing with new unit.",
    )

    return repo, wo_svc, verif_svc, inv, completed_wo


def test_missing_telemetry_produces_inconclusive_verdict(m5_verif_setup):
    """Missing post-maintenance telemetry MUST produce INCONCLUSIVE verdict, never success."""
    repo, wo_svc, verif_svc, inv, completed_wo = m5_verif_setup

    pre_feat = FeatureVector(
        feature_id="FV-PRE",
        machine_id="M21",
        timestamp=datetime.now(timezone.utc),
        vibration_rms=1.45,
        vibration_peak=2.10,
        temperature_mean=78.5,
    )
    pre_risk = FailureRisk(
        risk_id="RISK-PRE",
        machine_id="M21",
        risk_score=0.95,
        failure_mode=FailureMode.BEARING_DEGRADATION,
    )

    # Call verify_recovery with post_features and post_risk as None (missing telemetry)
    verif = verif_svc.verify_recovery(
        work_order_id=completed_wo.work_order_id,
        investigation_id=inv.investigation_id,
        machine_id="M21",
        pre_features=pre_feat,
        post_features=None,
        pre_risk=pre_risk,
        post_risk=None,
    )

    assert verif.verification_status == VerificationStatus.INCONCLUSIVE
    assert not verif.is_recovered
    assert "missing or incomplete" in verif.verification_reason.lower()

    # Work order must remain COMPLETED, NOT verified
    wo = repo.get_work_order(completed_wo.work_order_id)
    assert wo.status == WorkOrderStatus.COMPLETED

    # Investigation must NOT be closed
    persisted_inv = repo.get_investigation(inv.investigation_id)
    assert persisted_inv.status != InvestigationStatus.CLOSED

    # Verify ActionOutcome was recorded
    outcomes = repo.list_action_outcomes(machine_id="M21")
    assert len(outcomes) >= 1
    assert outcomes[0].verification_status == VerificationStatus.INCONCLUSIVE
    assert not outcomes[0].observed_failure_confirmed


def test_persisting_anomalies_produce_verification_failed(m5_verif_setup):
    """Post-maintenance telemetry with abnormal vibration produces FAILED verification."""
    repo, wo_svc, verif_svc, inv, completed_wo = m5_verif_setup

    pre_feat = FeatureVector(
        feature_id="FV-PRE-2",
        machine_id="M21",
        timestamp=datetime.now(timezone.utc),
        vibration_rms=1.45,
        vibration_peak=2.10,
        temperature_mean=78.5,
    )
    pre_risk = FailureRisk(
        risk_id="RISK-PRE-2",
        machine_id="M21",
        risk_score=0.95,
        failure_mode=FailureMode.BEARING_DEGRADATION,
    )

    post_feat = FeatureVector(
        feature_id="FV-POST-2",
        machine_id="M21",
        timestamp=datetime.now(timezone.utc),
        vibration_rms=1.20,  # Still way above 0.50 threshold
        vibration_peak=1.80,
        temperature_mean=74.0,
    )
    post_risk = FailureRisk(
        risk_id="RISK-POST-2",
        machine_id="M21",
        risk_score=0.85,
        failure_mode=FailureMode.BEARING_DEGRADATION,
    )

    verif = verif_svc.verify_recovery(
        work_order_id=completed_wo.work_order_id,
        investigation_id=inv.investigation_id,
        machine_id="M21",
        pre_features=pre_feat,
        post_features=post_feat,
        pre_risk=pre_risk,
        post_risk=post_risk,
    )

    assert verif.verification_status in (VerificationStatus.FAILED, VerificationStatus.VERIFICATION_FAILED)
    assert not verif.is_recovered

    # Work order is NOT verified
    wo = repo.get_work_order(completed_wo.work_order_id)
    assert wo.status == WorkOrderStatus.COMPLETED

    # Investigation is marked VERIFICATION_FAILED
    persisted_inv = repo.get_investigation(inv.investigation_id)
    assert persisted_inv.status == InvestigationStatus.VERIFICATION_FAILED

    # ActionOutcome recorded as failed
    outcomes = repo.list_action_outcomes(machine_id="M21")
    assert len(outcomes) >= 1
    assert outcomes[0].verification_status in (VerificationStatus.FAILED, VerificationStatus.VERIFICATION_FAILED)


def test_nominal_telemetry_verifies_and_records_closed_loop_outcome(m5_verif_setup):
    """Nominal post-maintenance telemetry produces VERIFIED and creates learning ActionOutcome."""
    repo, wo_svc, verif_svc, inv, completed_wo = m5_verif_setup

    pre_feat = FeatureVector(
        feature_id="FV-PRE-3",
        machine_id="M21",
        timestamp=datetime.now(timezone.utc),
        vibration_rms=1.45,
        vibration_peak=2.10,
        temperature_mean=78.5,
    )
    pre_risk = FailureRisk(
        risk_id="RISK-PRE-3",
        machine_id="M21",
        risk_score=0.95,
        failure_mode=FailureMode.BEARING_DEGRADATION,
    )

    post_feat = FeatureVector(
        feature_id="FV-POST-3",
        machine_id="M21",
        timestamp=datetime.now(timezone.utc),
        vibration_rms=0.42,  # Below 0.50 threshold
        vibration_peak=0.60,
        temperature_mean=58.0,  # Below 65.0 threshold
    )
    post_risk = FailureRisk(
        risk_id="RISK-POST-3",
        machine_id="M21",
        risk_score=0.12,  # Below 0.25 threshold
        failure_mode=FailureMode.NORMAL_OPERATION,
    )

    verif = verif_svc.verify_recovery(
        work_order_id=completed_wo.work_order_id,
        investigation_id=inv.investigation_id,
        machine_id="M21",
        pre_features=pre_feat,
        post_features=post_feat,
        pre_risk=pre_risk,
        post_risk=post_risk,
        action_proposal_id="PROP-M5-001",
        prediction_id="PRED-000322",
        downtime_avoided_hours=8.5,
    )

    assert verif.verification_status == VerificationStatus.VERIFIED
    assert verif.is_recovered

    # Work order is VERIFIED
    wo = repo.get_work_order(completed_wo.work_order_id)
    assert wo.status == WorkOrderStatus.VERIFIED

    # Investigation is CLOSED
    persisted_inv = repo.get_investigation(inv.investigation_id)
    assert persisted_inv.status == InvestigationStatus.CLOSED

    # Machine health updated to HEALTHY
    machine = repo.get_machine("M21")
    assert machine.health_status == HealthStatus.HEALTHY

    # Closed-loop learning record saved
    outcomes = repo.list_action_outcomes(machine_id="M21")
    assert len(outcomes) >= 1
    m21_outcome = outcomes[0]
    assert m21_outcome.action_proposal_id == "PROP-M5-001"
    assert m21_outcome.prediction_id == "PRED-000322"
    assert m21_outcome.verification_status == VerificationStatus.VERIFIED
    assert m21_outcome.observed_failure_confirmed
    assert m21_outcome.downtime_avoided_hours == 8.5
