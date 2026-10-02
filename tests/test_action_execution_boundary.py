"""Focused unit and boundary tests for M6.5.5.3B Governed Action Execution & Verification Boundary.

Covers:
A. Actor validation (blank, autonomous, system, valid human)
B. Approval validation (unapproved, missing approval, pending, expired)
C. Precondition failure (transitions to EXECUTION_BLOCKED, distinct from execution failure)
D. Action resolution (INSPECT_BEARING_ASSEMBLY -> create_work_order)
E. Inspection work-order creation (title, description, checklist, machine, component)
F. Unsupported action rejection (UnsupportedOperationError)
G. Idempotent execution (zero duplicate work orders, zero duplicate executions)
H. Execution failure (tool exception -> FAILED)
I. Verification: VERIFIED (post-action telemetry within limits)
J. Verification: PARTIALLY_VERIFIED (partial reduction)
K. Verification: VERIFICATION_FAILED (persisting abnormal conditions)
L. Verification: INCONCLUSIVE (missing telemetry never succeeds)
M. Execution success != Verification success (execution creates work order; telemetry governs verification)
N. ACTION_AUDIT persistence
O. ACTION_OUTCOME links proposal, execution, verification, simulated flag, and provenance
P. No inventory reservation for inspection (SP-002 untouched)
Q. No automatic technician assignment (assigned_to is None)
R. Streamlit cannot execute directly (static audit)
S. Rerun cannot execute twice (idempotency stability)
T. Repository parity (InMemoryRepository vs SnowflakeRepository signatures)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
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
from domain.exceptions import (
    ApprovalExpiredError,
    ApprovalRequiredError,
    UnsupportedOperationError,
)
from domain.models import (
    ActionExecution,
    ActionOutcome,
    ActionProposal,
    Approval,
    Component,
    FailureRisk,
    FeatureVector,
    Investigation,
    Machine,
    SparePart,
    Verification,
    WorkOrder,
)
from repositories.memory.memory_repository import InMemoryRepository
from repositories.snowflake.snowflake_repository import SnowflakeRepository
from services.action_execution_service import ActionExecutionService
from services.action_precondition_service import ActionPreconditionService
from services.approval_service import ApprovalService
from services.verification_service import VerificationPolicy, VerificationService
from services.work_order_service import WorkOrderService
from tools.actions.action_registry import create_m5_action_registry


@pytest.fixture
def isolated_env():
    """Create a completely isolated test environment on non-M21 test machine."""
    repo = InMemoryRepository()

    # Seed isolated test machine (NOT M21)
    test_machine = Machine(
        machine_id="TEST-M99",
        line_id="L-TEST",
        machine_code="M99",
        name="Test Isolated Conveyor 99",
        asset_type="CONVEYOR",
        criticality="HIGH",
        health_status=HealthStatus.DEGRADING,
    )
    repo._machines["TEST-M99"] = test_machine
    repo._components["TEST-M99"] = [
        Component(
            component_id="C-M99-BRG",
            machine_id="TEST-M99",
            name="Drive-End Bearing",
            component_type="BEARING",
        )
    ]

    # Seed an isolated investigation
    inv = Investigation(
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        component_id="C-M99-BRG",
        status=InvestigationStatus.RECOMMENDATION_READY,
        failure_mode=FailureMode.BEARING_DEGRADATION,
    )
    repo.create_investigation(inv)

    # repo already seeds SP-002 (stock=0, lead_time=5) and other available parts on seed=True

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
    verif_svc = VerificationService(
        repository=repo,
        maintenance_repo=repo,
        investigation_repo=repo,
        machine_repo=repo,
    )
    exec_svc = ActionExecutionService(
        governance_repo=repo,
        action_registry=action_reg,
        precondition_service=precondition_svc,
        approval_service=app_svc,
        verification_service=verif_svc,
    )
    return repo, app_svc, wo_svc, action_reg, precondition_svc, verif_svc, exec_svc


# ==============================================================================
# A. ACTOR VALIDATION
# ==============================================================================

def test_actor_validation_blank_or_whitespace_rejected(isolated_env):
    """Empty or whitespace caller_actor must be rejected with ValueError."""
    repo, _, _, _, _, _, exec_svc = isolated_env

    for blank in ["", "   ", "\t\n"]:
        with pytest.raises(ValueError, match="cannot be empty"):
            exec_svc.execute_proposal("PROP-ANY", caller_actor=blank)


def test_actor_validation_autonomous_agents_rejected(isolated_env):
    """Autonomous agents and bots must be rejected with PermissionError."""
    repo, _, _, _, _, _, exec_svc = isolated_env

    disallowed_actors = [
        "ReliabilityAgent",
        "reliabilityagent-v2",
        "coco",
        "coco_agent",
        "bot-executor",
        "orchestrator",
        "pipeline_daemon",
        "ml_engine",
        "systemagent",
    ]
    for actor in disallowed_actors:
        with pytest.raises(PermissionError, match="autonomous agent or system process"):
            exec_svc.execute_proposal("PROP-ANY", caller_actor=actor)


def test_actor_validation_system_process_rejected(isolated_env):
    """System process actors like 'SYSTEM' or 'system.process' must be rejected with PermissionError."""
    repo, _, _, _, _, _, exec_svc = isolated_env

    for system_actor in ["SYSTEM", "system", "system.process", "system_worker"]:
        with pytest.raises(PermissionError, match="autonomous agent or system process"):
            exec_svc.execute_proposal("PROP-ANY", caller_actor=system_actor)


def test_actor_validation_valid_human_operator_passes_actor_check(isolated_env):
    """Valid human operator identity passes actor check (fails later on proposal lookup, not actor)."""
    repo, _, _, _, _, _, exec_svc = isolated_env

    for human in ["shubham.r", "operator.john", "maintenance.lead"]:
        with pytest.raises(ValueError, match="ActionProposal 'PROP-NOTFOUND' not found"):
            exec_svc.execute_proposal("PROP-NOTFOUND", caller_actor=human)


# ==============================================================================
# B. APPROVAL VALIDATION
# ==============================================================================

def test_approval_validation_unapproved_proposal_rejected(isolated_env):
    """Executing a proposal in PROPOSED or PENDING_APPROVAL status is rejected."""
    repo, _, _, _, _, _, exec_svc = isolated_env

    prop = ActionProposal(
        proposal_id="PROP-B-UNAPPROVED",
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        action_type="INSPECT_BEARING_ASSEMBLY",
        reason="Bearing vibration",
        status=ActionProposalStatus.PROPOSED.value,
    )
    repo.save_action_proposal(prop)

    with pytest.raises(ApprovalRequiredError, match="must be 'APPROVED'"):
        exec_svc.execute_proposal("PROP-B-UNAPPROVED", caller_actor="shubham.r")


def test_approval_validation_missing_approval_record_rejected(isolated_env):
    """Executing a proposal with status APPROVED but no linked Approval is rejected."""
    repo, _, _, _, _, _, exec_svc = isolated_env

    prop = ActionProposal(
        proposal_id="PROP-B-NO-APPROVAL-REC",
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        action_type="INSPECT_BEARING_ASSEMBLY",
        reason="Bearing vibration",
        status=ActionProposalStatus.APPROVED.value,
    )
    repo.save_action_proposal(prop)

    with pytest.raises(ApprovalRequiredError, match="Linked Approval 'APP-PROP-B-NO-APPROVAL-REC' not found"):
        exec_svc.execute_proposal("PROP-B-NO-APPROVAL-REC", caller_actor="shubham.r")


def test_approval_validation_pending_approval_rejected(isolated_env):
    """Executing a proposal whose linked Approval is PENDING is rejected."""
    repo, _, _, _, _, _, exec_svc = isolated_env

    prop = ActionProposal(
        proposal_id="PROP-B-PENDING-APP",
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        action_type="INSPECT_BEARING_ASSEMBLY",
        reason="Bearing vibration",
        status=ActionProposalStatus.APPROVED.value,
    )
    repo.save_action_proposal(prop)

    app = Approval(
        approval_id="APP-PROP-B-PENDING-APP",
        action_proposal_id="PROP-B-PENDING-APP",
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        status=ApprovalStatus.PENDING,
    )
    repo.create_approval(app)

    with pytest.raises(ApprovalRequiredError, match="must be 'APPROVED'"):
        exec_svc.execute_proposal("PROP-B-PENDING-APP", caller_actor="shubham.r")


def test_approval_validation_expired_approval_rejected(isolated_env):
    """Executing a proposal whose linked Approval is expired is rejected."""
    repo, _, _, _, _, _, exec_svc = isolated_env

    prop = ActionProposal(
        proposal_id="PROP-B-EXPIRED",
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        action_type="INSPECT_BEARING_ASSEMBLY",
        reason="Bearing vibration",
        status=ActionProposalStatus.APPROVED.value,
    )
    repo.save_action_proposal(prop)

    app = Approval(
        approval_id="APP-PROP-B-EXPIRED",
        action_proposal_id="PROP-B-EXPIRED",
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        status=ApprovalStatus.APPROVED,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    repo.create_approval(app)

    with pytest.raises(ApprovalExpiredError, match="expired at"):
        exec_svc.execute_proposal("PROP-B-EXPIRED", caller_actor="shubham.r")


# ==============================================================================
# C. PRECONDITION FAILURE
# ==============================================================================

def test_precondition_failure_transitions_to_execution_blocked(isolated_env):
    """Precondition failure sets proposal status to EXECUTION_BLOCKED and logs audit."""
    repo, _, _, _, _, _, exec_svc = isolated_env

    prop = ActionProposal(
        proposal_id="PROP-C-STOCKOUT",
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        action_type="RESERVE_SPARE_PART",
        reason="Stockout test",
        status=ActionProposalStatus.APPROVED.value,
        parameters={"part_id": "SP-002", "qty": 1},
    )
    repo.save_action_proposal(prop)

    app = Approval(
        approval_id="APP-PROP-C-STOCKOUT",
        action_proposal_id="PROP-C-STOCKOUT",
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        status=ApprovalStatus.APPROVED,
    )
    repo.create_approval(app)

    execution = exec_svc.execute_proposal("PROP-C-STOCKOUT", caller_actor="shubham.r")

    assert execution.status == "FAILED"
    assert "SP-002" in execution.error_message

    persisted_prop = repo.get_action_proposal("PROP-C-STOCKOUT")
    assert persisted_prop.status == ActionProposalStatus.EXECUTION_BLOCKED.value

    # Audit event recorded
    audits = repo.list_audit_events()
    blocked_audits = [a for a in audits if a.action_type == "ACTION_EXECUTION_BLOCKED_PRECONDITIONS"]
    assert len(blocked_audits) == 1
    assert blocked_audits[0].actor == "shubham.r"


# ==============================================================================
# D & E. ACTION RESOLUTION & INSPECTION WORK-ORDER CREATION
# ==============================================================================

def test_inspection_action_resolves_to_work_order_without_inventory_or_assignment(isolated_env):
    """INSPECT_BEARING_ASSEMBLY creates an inspection work order, no parts reserved, no tech assigned."""
    repo, _, _, _, _, _, exec_svc = isolated_env

    prop = ActionProposal(
        proposal_id="PROP-D-INSPECT",
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        component_id="C-M99-BRG",
        action_type="INSPECT_BEARING_ASSEMBLY",
        priority=Priority.HIGH,
        reason="High vibration RMS on drive-end bearing",
        status=ActionProposalStatus.APPROVED.value,
        parameters={
            "title": "Inspect Conveyor Drive-End Bearing",
            "action_description": "Perform vibration analysis and visual inspection on C-M99-BRG.",
            "suggested_checklist": [
                "Verify LOTO applied",
                "Measure acoustic emission",
                "Check lubrication status",
            ],
            "estimated_downtime_hours": 1.5,
        },
        idempotency_key="IDEM-D-INSPECT-001",
    )
    repo.save_action_proposal(prop)

    app = Approval(
        approval_id="APP-PROP-D-INSPECT",
        action_proposal_id="PROP-D-INSPECT",
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        status=ApprovalStatus.APPROVED,
    )
    repo.create_approval(app)

    # Initial inventory check
    parts_before = {p.part_id: p.stock_qty for p in repo.list_spare_parts()}

    execution = exec_svc.execute_proposal("PROP-D-INSPECT", caller_actor="shubham.r")

    assert execution.status == "SUCCESS"
    assert "work_order_id" in execution.result_data

    # Verify work order
    wo_id = execution.result_data["work_order_id"]
    wo = repo.get_work_order(wo_id)
    assert wo is not None
    assert wo.machine_id == "TEST-M99"
    assert wo.component_id == "C-M99-BRG"
    assert wo.title == "Inspect Conveyor Drive-End Bearing"
    assert "vibration analysis" in wo.description
    assert len(wo.checklist) == 3
    assert "Verify LOTO applied" in wo.checklist

    # P. No inventory reservation
    parts_after = {p.part_id: p.stock_qty for p in repo.list_spare_parts()}
    assert parts_after == parts_before

    # Q. No automatic technician assignment
    assert wo.assigned_to is None
    assert wo.status == WorkOrderStatus.APPROVED

    # Proposal marked EXECUTED
    persisted_prop = repo.get_action_proposal("PROP-D-INSPECT")
    assert persisted_prop.status == ActionProposalStatus.EXECUTED.value


# ==============================================================================
# F. UNSUPPORTED ACTION REJECTION
# ==============================================================================

def test_unsupported_action_type_raises_typed_governance_error(isolated_env):
    """Unsupported action type raises UnsupportedOperationError without guessing."""
    repo, _, _, _, _, _, exec_svc = isolated_env

    prop = ActionProposal(
        proposal_id="PROP-F-UNKNOWN",
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        action_type="OVERCLOCK_SPINDLE_MOTOR",
        reason="Unknown action",
        status=ActionProposalStatus.APPROVED.value,
    )
    repo.save_action_proposal(prop)

    app = Approval(
        approval_id="APP-PROP-F-UNKNOWN",
        action_proposal_id="PROP-F-UNKNOWN",
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        status=ApprovalStatus.APPROVED,
    )
    repo.create_approval(app)

    with pytest.raises(UnsupportedOperationError, match="not supported"):
        exec_svc.execute_proposal("PROP-F-UNKNOWN", caller_actor="shubham.r")


# ==============================================================================
# G & S. IDEMPOTENT EXECUTION & RERUN SAFETY
# ==============================================================================

def test_idempotent_execution_creates_exactly_one_work_order(isolated_env):
    """Rerunning with identical proposal and idempotency key creates zero duplicate work orders."""
    repo, _, _, action_reg, _, _, exec_svc = isolated_env

    prop = ActionProposal(
        proposal_id="PROP-G-IDEM",
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        component_id="C-M99-BRG",
        action_type="INSPECT_BEARING_ASSEMBLY",
        reason="Idempotency test",
        status=ActionProposalStatus.APPROVED.value,
        parameters={"title": "Idempotent Inspection"},
        idempotency_key="IDEM-G-STABLE-999",
    )
    repo.save_action_proposal(prop)

    app = Approval(
        approval_id="APP-PROP-G-IDEM",
        action_proposal_id="PROP-G-IDEM",
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        status=ApprovalStatus.APPROVED,
    )
    repo.create_approval(app)

    # First call
    exec_1 = exec_svc.execute_proposal("PROP-G-IDEM", caller_actor="shubham.r", idempotency_key="IDEM-G-STABLE-999")
    assert exec_1.status == "SUCCESS"
    wo_id_1 = exec_1.result_data["work_order_id"]

    # Spy on execute_tool for the second call
    with patch.object(action_reg, "execute_tool", wraps=action_reg.execute_tool) as spy_tool:
        exec_2 = exec_svc.execute_proposal("PROP-G-IDEM", caller_actor="shubham.r", idempotency_key="IDEM-G-STABLE-999")
        spy_tool.assert_not_called()

    # Second call returns same execution
    assert exec_2.execution_id == exec_1.execution_id
    assert exec_2.result_data["work_order_id"] == wo_id_1

    # Only one execution in repo for this proposal
    executions = repo.list_action_executions(action_proposal_id="PROP-G-IDEM")
    assert len(executions) == 1


# ==============================================================================
# H. EXECUTION FAILURE
# ==============================================================================

def test_execution_failure_marks_execution_and_proposal_failed(isolated_env):
    """Tool raising exception records failed execution and transitions proposal to FAILED."""
    repo, _, _, action_reg, _, _, exec_svc = isolated_env

    prop = ActionProposal(
        proposal_id="PROP-H-FAIL",
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        component_id="C-M99-BRG",
        action_type="CREATE_WORK_ORDER",
        reason="Fail test",
        status=ActionProposalStatus.APPROVED.value,
        parameters={"title": "Failing Work Order"},
    )
    repo.save_action_proposal(prop)

    app = Approval(
        approval_id="APP-PROP-H-FAIL",
        action_proposal_id="PROP-H-FAIL",
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        status=ApprovalStatus.APPROVED,
    )
    repo.create_approval(app)

    with patch.object(action_reg, "execute_tool", side_effect=RuntimeError("ERP connectivity drop")):
        with pytest.raises(RuntimeError, match="ERP connectivity drop"):
            exec_svc.execute_proposal("PROP-H-FAIL", caller_actor="shubham.r")

    persisted_prop = repo.get_action_proposal("PROP-H-FAIL")
    assert persisted_prop.status == ActionProposalStatus.FAILED.value

    executions = repo.list_action_executions(action_proposal_id="PROP-H-FAIL")
    assert len(executions) == 1
    assert executions[0].status == "FAILED"
    assert "ERP connectivity drop" in executions[0].error_message


# ==============================================================================
# I, J, K, L, M, O. EXECUTION -> VERIFICATION -> OUTCOME BRIDGE
# ==============================================================================

def test_execution_success_does_not_equal_verification_success(isolated_env):
    """M: Execution success creates work order; physical verification is independent and requires telemetry."""
    repo, _, wo_svc, _, _, verif_svc, exec_svc = isolated_env

    prop = ActionProposal(
        proposal_id="PROP-BRIDGE-01",
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        component_id="C-M99-BRG",
        action_type="INSPECT_BEARING_ASSEMBLY",
        reason="Bridge test",
        status=ActionProposalStatus.APPROVED.value,
        parameters={"title": "Bridge Inspection Work Order"},
    )
    repo.save_action_proposal(prop)

    app = Approval(
        approval_id="APP-PROP-BRIDGE-01",
        action_proposal_id="PROP-BRIDGE-01",
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        status=ApprovalStatus.APPROVED,
    )
    repo.create_approval(app)

    # Step 1: Execute proposal
    exec_record = exec_svc.execute_proposal("PROP-BRIDGE-01", caller_actor="shubham.r")
    assert exec_record.status == "SUCCESS"
    wo_id = exec_record.result_data["work_order_id"]

    # Crucial M assertion: work order is APPROVED, proposal is EXECUTED, machine is still DEGRADING
    machine = repo.get_machine("TEST-M99")
    assert machine.health_status == HealthStatus.DEGRADING
    assert repo.get_work_order(wo_id).status == WorkOrderStatus.APPROVED

    # Step 2: Technician completes work order
    wo_svc.complete_work_order(wo_id, technician_name="tech.john", duration_hours=1.0, notes="Inspection finished.")
    assert repo.get_work_order(wo_id).status == WorkOrderStatus.COMPLETED

    # Step 3: L - Verification without telemetry is INCONCLUSIVE, not VERIFIED
    inconclusive_res = verif_svc.verify_recovery(
        work_order_id=wo_id,
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        action_proposal_id="PROP-BRIDGE-01",
        execution_id=exec_record.execution_id,
        pre_features=None,
        post_features=None,
        pre_risk=None,
        post_risk=None,
        is_simulated_telemetry=True,
    )
    assert inconclusive_res.verification_status == VerificationStatus.INCONCLUSIVE
    assert not inconclusive_res.is_recovered

    # Verify ActionOutcome was recorded and links execution + proposal
    outcomes = repo.list_action_outcomes(machine_id="TEST-M99")
    assert len(outcomes) == 1
    out = outcomes[0]
    assert out.action_proposal_id == "PROP-BRIDGE-01"
    assert out.execution_id == exec_record.execution_id
    assert out.verification_id == inconclusive_res.verification_id
    assert out.verification_status == VerificationStatus.INCONCLUSIVE
    assert out.is_simulated_telemetry is True


def test_verification_lifecycle_verified(isolated_env):
    """I: Post-action healthy telemetry produces VERIFIED, updates machine to HEALTHY, closes investigation."""
    repo, _, wo_svc, _, _, verif_svc, exec_svc = isolated_env

    prop = ActionProposal(
        proposal_id="PROP-VERIF-OK",
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        component_id="C-M99-BRG",
        action_type="INSPECT_BEARING_ASSEMBLY",
        reason="Bearing recovery test",
        status=ActionProposalStatus.APPROVED.value,
        parameters={"title": "Recovery Inspection"},
    )
    repo.save_action_proposal(prop)

    app = Approval(
        approval_id="APP-PROP-VERIF-OK",
        action_proposal_id="PROP-VERIF-OK",
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        status=ApprovalStatus.APPROVED,
    )
    repo.create_approval(app)

    exec_record = exec_svc.execute_proposal("PROP-VERIF-OK", caller_actor="shubham.r")
    wo_id = exec_record.result_data["work_order_id"]
    wo_svc.complete_work_order(wo_id, technician_name="tech.john", duration_hours=1.0, notes="Done")

    now = datetime.now(timezone.utc)
    pre_feat = FeatureVector(feature_id="F-PRE", machine_id="TEST-M99", timestamp=now, vibration_rms=1.5, vibration_peak=2.0, temperature_mean=80.0)
    post_feat = FeatureVector(feature_id="F-POST", machine_id="TEST-M99", timestamp=now, vibration_rms=0.35, vibration_peak=0.5, temperature_mean=55.0)
    pre_r = FailureRisk(risk_id="R-PRE", machine_id="TEST-M99", risk_score=0.90, failure_mode=FailureMode.BEARING_DEGRADATION)
    post_r = FailureRisk(risk_id="R-POST", machine_id="TEST-M99", risk_score=0.10, failure_mode=FailureMode.NORMAL_OPERATION)

    verif = exec_svc.verify_proposal_execution(
        proposal_id="PROP-VERIF-OK",
        execution_id=exec_record.execution_id,
        work_order_id=wo_id,
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        pre_features=pre_feat,
        post_features=post_feat,
        pre_risk=pre_r,
        post_risk=post_r,
        is_simulated_telemetry=True,
        telemetry_provenance={"sensor_window": "2026-10-03T00:00:00Z to 2026-10-03T02:00:00Z", "source": "SIM_SENSOR"},
    )

    assert verif.verification_status == VerificationStatus.VERIFIED
    assert verif.is_recovered is True
    assert verif.action_execution_id == exec_record.execution_id

    # O. ActionOutcome complete linkage
    outcomes = repo.list_action_outcomes(machine_id="TEST-M99")
    assert len(outcomes) == 1
    out = outcomes[0]
    assert out.action_proposal_id == "PROP-VERIF-OK"
    assert out.execution_id == exec_record.execution_id
    assert out.verification_id == verif.verification_id
    assert out.verification_status == VerificationStatus.VERIFIED
    assert out.is_simulated_telemetry is True
    assert out.telemetry_provenance["source"] == "SIM_SENSOR"

    # Governed lifecycle transitions
    assert repo.get_work_order(wo_id).status == WorkOrderStatus.VERIFIED
    assert repo.get_machine("TEST-M99").health_status == HealthStatus.HEALTHY
    assert repo.get_investigation("INV-TEST-99").status == InvestigationStatus.CLOSED
    assert repo.get_action_proposal("PROP-VERIF-OK").status == ActionProposalStatus.VERIFIED.value


def test_verification_lifecycle_partially_verified(isolated_env):
    """J: Partial improvement produces PARTIALLY_VERIFIED and marks investigation as REQUIRES_FOLLOW_UP."""
    repo, _, wo_svc, _, _, verif_svc, exec_svc = isolated_env

    prop = ActionProposal(
        proposal_id="PROP-VERIF-PARTIAL",
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        component_id="C-M99-BRG",
        action_type="INSPECT_BEARING_ASSEMBLY",
        reason="Partial test",
        status=ActionProposalStatus.APPROVED.value,
        parameters={"title": "Partial Inspection"},
    )
    repo.save_action_proposal(prop)

    app = Approval(
        approval_id="APP-PROP-VERIF-PARTIAL",
        action_proposal_id="PROP-VERIF-PARTIAL",
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        status=ApprovalStatus.APPROVED,
    )
    repo.create_approval(app)

    exec_record = exec_svc.execute_proposal("PROP-VERIF-PARTIAL", caller_actor="shubham.r")
    wo_id = exec_record.result_data["work_order_id"]
    wo_svc.complete_work_order(wo_id, technician_name="tech.john", duration_hours=1.0, notes="Done")

    now = datetime.now(timezone.utc)
    pre_feat = FeatureVector(feature_id="F-PRE", machine_id="TEST-M99", timestamp=now, vibration_rms=1.5, vibration_peak=2.0, temperature_mean=80.0)
    # Reduced by 60% from 1.5 to 0.60, but still above 0.50 threshold
    post_feat = FeatureVector(feature_id="F-POST", machine_id="TEST-M99", timestamp=now, vibration_rms=0.60, vibration_peak=0.8, temperature_mean=60.0)
    pre_r = FailureRisk(risk_id="R-PRE", machine_id="TEST-M99", risk_score=0.90, failure_mode=FailureMode.BEARING_DEGRADATION)
    post_r = FailureRisk(risk_id="R-POST", machine_id="TEST-M99", risk_score=0.40, failure_mode=FailureMode.BEARING_DEGRADATION)

    verif = exec_svc.verify_proposal_execution(
        proposal_id="PROP-VERIF-PARTIAL",
        execution_id=exec_record.execution_id,
        work_order_id=wo_id,
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        pre_features=pre_feat,
        post_features=post_feat,
        pre_risk=pre_r,
        post_risk=post_r,
        is_simulated_telemetry=True,
    )

    assert verif.verification_status == VerificationStatus.PARTIALLY_VERIFIED
    assert verif.is_recovered is False
    assert repo.get_investigation("INV-TEST-99").status == InvestigationStatus.REQUIRES_FOLLOW_UP


def test_verification_lifecycle_failed(isolated_env):
    """K: Persisting abnormal conditions produce FAILED, marking investigation as VERIFICATION_FAILED."""
    repo, _, wo_svc, _, _, verif_svc, exec_svc = isolated_env

    prop = ActionProposal(
        proposal_id="PROP-VERIF-FAIL",
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        component_id="C-M99-BRG",
        action_type="INSPECT_BEARING_ASSEMBLY",
        reason="Fail test",
        status=ActionProposalStatus.APPROVED.value,
        parameters={"title": "Failed Inspection"},
    )
    repo.save_action_proposal(prop)

    app = Approval(
        approval_id="APP-PROP-VERIF-FAIL",
        action_proposal_id="PROP-VERIF-FAIL",
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        status=ApprovalStatus.APPROVED,
    )
    repo.create_approval(app)

    exec_record = exec_svc.execute_proposal("PROP-VERIF-FAIL", caller_actor="shubham.r")
    wo_id = exec_record.result_data["work_order_id"]
    wo_svc.complete_work_order(wo_id, technician_name="tech.john", duration_hours=1.0, notes="Done")

    now = datetime.now(timezone.utc)
    pre_feat = FeatureVector(feature_id="F-PRE", machine_id="TEST-M99", timestamp=now, vibration_rms=1.5, vibration_peak=2.0, temperature_mean=80.0)
    post_feat = FeatureVector(feature_id="F-POST", machine_id="TEST-M99", timestamp=now, vibration_rms=1.6, vibration_peak=2.2, temperature_mean=85.0)
    pre_r = FailureRisk(risk_id="R-PRE", machine_id="TEST-M99", risk_score=0.90, failure_mode=FailureMode.BEARING_DEGRADATION)
    post_r = FailureRisk(risk_id="R-POST", machine_id="TEST-M99", risk_score=0.95, failure_mode=FailureMode.BEARING_DEGRADATION)

    verif = exec_svc.verify_proposal_execution(
        proposal_id="PROP-VERIF-FAIL",
        execution_id=exec_record.execution_id,
        work_order_id=wo_id,
        investigation_id="INV-TEST-99",
        machine_id="TEST-M99",
        pre_features=pre_feat,
        post_features=post_feat,
        pre_risk=pre_r,
        post_risk=post_r,
        is_simulated_telemetry=True,
    )

    assert verif.verification_status == VerificationStatus.FAILED
    assert verif.is_recovered is False
    assert repo.get_investigation("INV-TEST-99").status == InvestigationStatus.VERIFICATION_FAILED
    assert repo.get_action_proposal("PROP-VERIF-FAIL").status == ActionProposalStatus.VERIFICATION_FAILED.value


# ==============================================================================
# R. STREAMLIT CANNOT EXECUTE DIRECTLY
# ==============================================================================

def test_streamlit_views_have_zero_direct_execution_calls():
    """R: Static code analysis proves Streamlit views contain zero execution calls."""
    import inspect
    from app.streamlit.views import investigations
    from app.streamlit.components import approvals

    inv_source = inspect.getsource(investigations)
    app_source = inspect.getsource(approvals)

    forbidden_calls = [
        "execute_proposal",
        "ActionExecutionService",
        "CreateWorkOrderAction",
        "execute_tool",
    ]
    for call in forbidden_calls:
        assert call not in inv_source, f"Forbidden call '{call}' found in investigations.py"
        assert call not in app_source, f"Forbidden call '{call}' found in approvals.py"


# ==============================================================================
# T. REPOSITORY PARITY
# ==============================================================================

def test_repository_parity_action_execution_and_outcome():
    """T: Both InMemoryRepository and SnowflakeRepository implement all governance methods."""
    in_mem_methods = dir(InMemoryRepository)
    snowflake_methods = dir(SnowflakeRepository)

    required_methods = [
        "save_action_execution",
        "get_action_execution",
        "list_action_executions",
        "save_action_outcome",
        "get_action_outcome",
        "list_action_outcomes",
        "save_verification",
        "get_verification",
        "log_audit",
        "list_audit_events",
    ]
    for method in required_methods:
        assert method in in_mem_methods, f"InMemoryRepository missing '{method}'"
        assert method in snowflake_methods, f"SnowflakeRepository missing '{method}'"
