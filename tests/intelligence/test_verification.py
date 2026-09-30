"""Verification and closed-loop reliability recovery tests.

Follows AGENT.md & architecture/architecture.md:
- Work order completion != verification success
- Verification evaluates measured physical sensor signals against VerificationPolicy
- Supports VERIFIED, PARTIALLY_VERIFIED, and FAILED outcomes
- Governs lifecycle transitions:
  * VERIFIED: Investigation -> CLOSED, WorkOrder -> VERIFIED, Machine -> HEALTHY
  * PARTIALLY_VERIFIED: Investigation -> REQUIRES_FOLLOW_UP
  * FAILED: Investigation -> VERIFICATION_FAILED (WorkOrder remains COMPLETED, NOT verified)
"""

from datetime import datetime, timezone
import pytest

from domain.enums import (
    FailureMode,
    HealthStatus,
    InvestigationStatus,
    Priority,
    RiskLevel,
    Severity,
    VerificationStatus,
    WorkOrderStatus,
)
from domain.models import (
    Anomaly,
    FailureRisk,
    FeatureVector,
    Investigation,
    WorkOrder,
)
from repositories.memory.memory_repository import InMemoryRepository
from services.oee_service import OEEResult
from services.verification_service import VerificationPolicy, VerificationService
from services.work_order_service import WorkOrderService


@pytest.fixture
def verification_setup():
    repo = InMemoryRepository()
    wo_svc = WorkOrderService(repository=repo, governance_repo=repo)
    verif_svc = VerificationService(
        repository=repo,
        maintenance_repo=repo,
        investigation_repo=repo,
        machine_repo=repo,
    )

    # Seed baseline investigation
    inv = Investigation(
        investigation_id="INV-VERIF-001",
        machine_id="M204",
        status=InvestigationStatus.PENDING_APPROVAL,
    )
    repo.create_investigation(inv)

    # Seed work order
    wo = WorkOrder(
        work_order_id="WO-VERIF-001",
        machine_id="M204",
        component_id="COMP-M204-BRG-DE",
        investigation_id=inv.investigation_id,
        title="Replace bearing",
        description="Physical replacement",
        failure_mode=FailureMode.BEARING_DEGRADATION,
        priority=Priority.HIGH,
        status=WorkOrderStatus.APPROVED,
    )
    wo_svc.create_work_order(wo)

    return repo, wo_svc, verif_svc, inv, wo


def test_work_order_completion_does_not_equal_verification(verification_setup):
    """Technician completing work order sets status to COMPLETED, not VERIFIED."""
    repo, wo_svc, verif_svc, inv, wo = verification_setup

    completed_wo, maint_event = wo_svc.complete_work_order(
        work_order_id=wo.work_order_id,
        technician_name="tech.marcus",
        duration_hours=2.0,
        notes="Replaced bearing with new SKF 6205.",
    )

    assert completed_wo.status == WorkOrderStatus.COMPLETED
    assert completed_wo.completed_at is not None
    assert maint_event.work_order_id == wo.work_order_id

    # Verify that investigation remains untouched until verification service runs
    persisted_inv = repo.get_investigation(inv.investigation_id)
    assert persisted_inv.status == InvestigationStatus.PENDING_APPROVAL


def test_successful_verification_closes_investigation_and_verifies_work_order(verification_setup):
    """When post-maintenance telemetry returns to nominal, outcome is VERIFIED and investigation closes."""
    repo, wo_svc, verif_svc, inv, wo = verification_setup
    completed_wo, _ = wo_svc.complete_work_order(
        work_order_id=wo.work_order_id,
        technician_name="tech.marcus",
        duration_hours=2.0,
        notes="Bearing replaced.",
    )

    now = datetime.now(timezone.utc)
    pre_features = FeatureVector(
        feature_id="FV-PRE",
        machine_id="M204",
        timestamp=now,
        vibration_rms=0.920,
        vibration_peak=1.95,
        temperature_mean=84.0,
    )
    post_features = FeatureVector(
        feature_id="FV-POST",
        machine_id="M204",
        timestamp=now,
        vibration_rms=0.435,  # Nominal healthy
        vibration_peak=0.62,
        temperature_mean=58.2,  # Nominal healthy
    )
    pre_risk = FailureRisk(
        risk_id="RSK-PRE",
        machine_id="M204",
        failure_mode=FailureMode.BEARING_DEGRADATION,
        risk_score=0.88,
        risk_level=RiskLevel.CRITICAL,
    )
    post_risk = FailureRisk(
        risk_id="RSK-POST",
        machine_id="M204",
        failure_mode=FailureMode.BEARING_DEGRADATION,
        risk_score=0.10,
        risk_level=RiskLevel.LOW,
    )

    verif = verif_svc.verify_recovery(
        work_order_id=completed_wo.work_order_id,
        investigation_id=inv.investigation_id,
        machine_id="M204",
        pre_features=pre_features,
        post_features=post_features,
        pre_risk=pre_risk,
        post_risk=post_risk,
        active_anomalies=[],
        verifier="lead.engineer",
    )

    assert verif.verification_status == VerificationStatus.VERIFIED
    assert verif.is_recovered is True
    assert verif.risk_delta < 0

    # Lifecycle assertions
    updated_inv = repo.get_investigation(inv.investigation_id)
    assert updated_inv.status == InvestigationStatus.CLOSED
    assert updated_inv.closed_at is not None

    updated_wo = repo.get_work_order(wo.work_order_id)
    assert updated_wo.status == WorkOrderStatus.VERIFIED

    machine = repo.get_machine("M204")
    assert machine.health_status == HealthStatus.HEALTHY


def test_failed_verification_preserves_completed_work_order_and_marks_failure(verification_setup):
    """When post-maintenance telemetry remains abnormal, outcome is FAILED."""
    repo, wo_svc, verif_svc, inv, wo = verification_setup
    completed_wo, _ = wo_svc.complete_work_order(
        work_order_id=wo.work_order_id,
        technician_name="tech.marcus",
        duration_hours=2.0,
        notes="Replaced bearing with wrong part.",
    )

    now = datetime.now(timezone.utc)
    pre_features = FeatureVector(
        feature_id="FV-PRE",
        machine_id="M204",
        timestamp=now,
        vibration_rms=0.920,
        vibration_peak=1.95,
        temperature_mean=84.0,
    )
    # Post telemetry is still high!
    post_features = FeatureVector(
        feature_id="FV-POST-BAD",
        machine_id="M204",
        timestamp=now,
        vibration_rms=0.860,  # Abnormal!
        vibration_peak=1.80,
        temperature_mean=79.5,  # Abnormal!
    )
    pre_risk = FailureRisk(
        risk_id="RSK-PRE",
        machine_id="M204",
        failure_mode=FailureMode.BEARING_DEGRADATION,
        risk_score=0.88,
        risk_level=RiskLevel.CRITICAL,
    )
    post_risk = FailureRisk(
        risk_id="RSK-POST-BAD",
        machine_id="M204",
        failure_mode=FailureMode.BEARING_DEGRADATION,
        risk_score=0.82,  # Still critical!
        risk_level=RiskLevel.CRITICAL,
    )

    verif = verif_svc.verify_recovery(
        work_order_id=completed_wo.work_order_id,
        investigation_id=inv.investigation_id,
        machine_id="M204",
        pre_features=pre_features,
        post_features=post_features,
        pre_risk=pre_risk,
        post_risk=post_risk,
        verifier="lead.engineer",
    )

    assert verif.verification_status == VerificationStatus.FAILED
    assert verif.is_recovered is False

    # Investigation marked as VERIFICATION_FAILED
    updated_inv = repo.get_investigation(inv.investigation_id)
    assert updated_inv.status == InvestigationStatus.VERIFICATION_FAILED

    # Work order remains COMPLETED (technician closed it, but verification rejected it!)
    updated_wo = repo.get_work_order(wo.work_order_id)
    assert updated_wo.status == WorkOrderStatus.COMPLETED
