"""Milestone 5 Flagship Integration Test: M21 Closed-Loop Reliability Scenario.

Validates the complete end-to-end product loop on canonical Grinder 3 (M21):
SENSE -> UNDERSTAND -> PREDICT -> INVESTIGATE -> RECOMMEND -> APPROVE -> ACT -> VERIFY -> LEARN

Canonical Entities:
- Machine: M21 (Grinder 3)
- Component: C-M21-BRG
- Sensors: S-M21-VIB, S-M21-BTMP
- Prediction: PRED-000322 (failure_prob=0.95, risk=HIGH)
- Spare Part: SP-002 (stock_qty=0, lead_time_days=5)

Safety & Governance Constraints:
1. CoCo cannot directly execute actions or self-approve.
2. Every consequential action passes through the human ApprovalGateway.
3. Strict zero-trust pipeline: Proposal -> Approval -> Preconditions -> Idempotent Execution -> Verification -> Learning Outcome.
4. SP-002 stockout fails safely with honest shortage reporting (no negative stock or fabricated parts).
5. Closed-loop outcome recorded for future training data without automated online retraining in M5.
"""

from datetime import datetime, timezone
import pytest

from domain.enums import (
    ActionProposalStatus,
    ApprovalStatus,
    FailureMode,
    HealthStatus,
    InvestigationStatus,
    Priority,
    VerificationStatus,
    WorkOrderStatus,
)
from domain.models import (
    ActionProposal,
    FailureRisk,
    FeatureVector,
    Investigation,
    WorkOrder,
)
from repositories.memory.memory_repository import InMemoryRepository
from services.action_execution_service import ActionExecutionService
from services.action_precondition_service import ActionPreconditionService
from services.approval_gateway import ApprovalGateway
from services.approval_service import ApprovalService
from services.verification_service import VerificationService
from services.work_order_service import WorkOrderService
from tools.actions.action_registry import create_m5_action_registry


def test_m21_flagship_closed_loop_workflow():
    """Complete flagship closed-loop test from PRED-000322 to ActionOutcome on M21."""
    # 0. Initialize System Architecture
    repo = InMemoryRepository()
    app_svc = ApprovalService(repository=repo)
    wo_svc = WorkOrderService(repository=repo, governance_repo=repo)
    action_reg = create_m5_action_registry(
        approval_service=app_svc,
        work_order_service=wo_svc,
        supply_chain_repo=repo,
        maintenance_repo=repo,
        governance_repo=repo,
    )
    precondition_svc = ActionPreconditionService(
        machine_repo=repo,
        maintenance_repo=repo,
        supply_chain_repo=repo,
        governance_repo=repo,
    )
    gateway = ApprovalGateway(repository=repo, approval_service=app_svc)
    exec_svc = ActionExecutionService(
        governance_repo=repo,
        action_registry=action_reg,
        precondition_service=precondition_svc,
        approval_service=app_svc,
    )
    verif_svc = VerificationService(
        repository=repo,
        maintenance_repo=repo,
        investigation_repo=repo,
        machine_repo=repo,
    )

    # 1. SENSE & PREDICT: Canonical Prediction PRED-000322 on M21
    cpred = repo.get_canonical_prediction("PRED-000322")
    assert cpred is not None
    assert cpred.machine_id == "M21"
    assert cpred.failure_prob == 0.95
    assert cpred.risk_level == "high"

    # 2. INVESTIGATE: CoCo Investigation
    inv = Investigation(
        investigation_id="INV-M21-000322",
        machine_id="M21",
        prediction_id="PRED-000322",
        status=InvestigationStatus.RECOMMENDATION_READY,
        summary="High-frequency bearing vibration anomaly detected on C-M21-BRG. Bearing degradation confirmed.",
    )
    repo.create_investigation(inv)

    # 3. RECOMMEND: Advisory Recommendation produces Action Proposal
    proposal = ActionProposal(
        proposal_id="PROP-M21-001",
        investigation_id=inv.investigation_id,
        machine_id="M21",
        action_type="CREATE_WORK_ORDER",
        priority=Priority.HIGH.value,
        reason="Imminent bearing failure detected by PRED-000322 on Grinder 3 (M21)",
        parameters={
            "component_id": "C-M21-BRG",
            "title": "Emergency Bearing Replacement - M21 Grinder 3",
            "description": "LOTO machine M21. Inspect and replace C-M21-BRG bearing assembly.",
            "assigned_to": "MAINT-CREW-1",
        },
        idempotency_key="IDEM-M21-WO-001",
    )
    submitted_proposal = gateway.submit_proposal(proposal)
    assert submitted_proposal.status == ActionProposalStatus.PENDING_APPROVAL.value

    # 4. APPROVE: Human Approval Boundary
    # Autonomous agent attempt is BLOCKED
    with pytest.raises(PermissionError):
        gateway.approve_proposal(
            proposal_id="PROP-M21-001",
            approver_id="ReliabilityAgent",
            reason="Automated self-approval attempt",
        )

    with pytest.raises(PermissionError):
        gateway.approve_proposal(
            proposal_id="PROP-M21-001",
            approver_id="CoCo",
            reason="LLM autonomous approval attempt",
        )

    # Human operator approves
    approval_record = gateway.approve_proposal(
        proposal_id="PROP-M21-001",
        approver_id="sarah.chen",
        reason="Verified vibration telemetry on S-M21-VIB exceeds safety thresholds. Approved replacement.",
    )
    assert approval_record.status == ApprovalStatus.APPROVED
    assert approval_record.decision_by == "sarah.chen"

    # 5. ACT: Zero-Trust Action Execution
    # Part reservation check: SP-002 is out of stock in canonical data
    preconditions = precondition_svc.validate_preconditions(
        action_type="RESERVE_SPARE_PART",
        machine_id="M21",
        part_id="SP-002",
        qty=1,
    )
    assert not preconditions.can_proceed
    assert preconditions.details["stock_qty"] == 0
    assert preconditions.details["lead_time_days"] == 5

    # Execute approved work order creation through zero-trust execution service
    execution = exec_svc.execute_proposal(
        proposal_id="PROP-M21-001",
        caller_actor="sarah.chen",
        idempotency_key="IDEM-M21-WO-001",
    )
    assert execution.status == "SUCCESS"
    assert "work_order_id" in execution.result_data

    wo_id = execution.result_data["work_order_id"]
    wo = repo.get_work_order(wo_id)
    assert wo is not None
    assert wo.machine_id == "M21"
    assert wo.component_id == "C-M21-BRG"

    # Maintenance technician completes the physical repair
    completed_wo, maint_event = wo_svc.complete_work_order(
        work_order_id=wo_id,
        technician_name="tech.marcus",
        duration_hours=3.5,
        notes="Replaced C-M21-BRG bearing assembly. Aligned spindle and tested rotation.",
    )
    assert completed_wo.status == WorkOrderStatus.COMPLETED

    # 6. VERIFY: Closed-Loop Physical Verification
    # Case A: Missing telemetry produces INCONCLUSIVE verdict
    inconclusive_verif = verif_svc.verify_recovery(
        work_order_id=wo_id,
        investigation_id=inv.investigation_id,
        machine_id="M21",
        pre_features=None,
        post_features=None,
        pre_risk=None,
        post_risk=None,
    )
    assert inconclusive_verif.verification_status == VerificationStatus.INCONCLUSIVE
    assert repo.get_work_order(wo_id).status == WorkOrderStatus.COMPLETED

    # Case B: Post-maintenance physical sensor telemetry normalizes
    pre_features = FeatureVector(
        feature_id="FV-M21-PRE",
        machine_id="M21",
        timestamp=datetime.now(timezone.utc),
        vibration_rms=1.65,
        vibration_peak=2.30,
        temperature_mean=82.0,
    )
    pre_risk = FailureRisk(
        risk_id="RISK-M21-PRE",
        machine_id="M21",
        risk_score=0.95,
        failure_mode=FailureMode.BEARING_DEGRADATION,
    )
    post_features = FeatureVector(
        feature_id="FV-M21-POST",
        machine_id="M21",
        timestamp=datetime.now(timezone.utc),
        vibration_rms=0.38,  # Well below 0.50 threshold
        vibration_peak=0.55,
        temperature_mean=55.0,  # Well below 65.0 threshold
    )
    post_risk = FailureRisk(
        risk_id="RISK-M21-POST",
        machine_id="M21",
        risk_score=0.10,  # Well below 0.25 threshold
        failure_mode=FailureMode.NORMAL_OPERATION,
    )

    verified_record = verif_svc.verify_recovery(
        work_order_id=wo_id,
        investigation_id=inv.investigation_id,
        machine_id="M21",
        pre_features=pre_features,
        post_features=post_features,
        pre_risk=pre_risk,
        post_risk=post_risk,
        action_proposal_id="PROP-M21-001",
        prediction_id="PRED-000322",
        downtime_avoided_hours=12.0,
    )
    assert verified_record.verification_status == VerificationStatus.VERIFIED
    assert verified_record.is_recovered

    # Work order is VERIFIED
    assert repo.get_work_order(wo_id).status == WorkOrderStatus.VERIFIED

    # Investigation is CLOSED
    assert repo.get_investigation(inv.investigation_id).status == InvestigationStatus.CLOSED

    # Machine health is HEALTHY
    assert repo.get_machine("M21").health_status == HealthStatus.HEALTHY

    # 7. LEARN: Closed-Loop Outcome Recorded
    outcomes = repo.list_action_outcomes(machine_id="M21")
    assert len(outcomes) >= 1
    m21_outcome = outcomes[0]
    assert m21_outcome.action_proposal_id == "PROP-M21-001"
    assert m21_outcome.prediction_id == "PRED-000322"
    assert m21_outcome.work_order_id == wo_id
    assert m21_outcome.verification_status == VerificationStatus.VERIFIED
    assert m21_outcome.observed_failure_confirmed
    assert m21_outcome.downtime_avoided_hours == 12.0
