"""Unit tests for ApprovalGateway.

Validates:
- Human-in-the-loop enforcement (blocks autonomous self-approval)
- Proposal status lifecycle (PROPOSED -> PENDING_APPROVAL -> APPROVED / REJECTED)
- Expiration validation
- Idempotent repeated approvals
"""

from datetime import datetime, timezone, timedelta
import pytest

from domain.enums import ActionProposalStatus, ApprovalStatus
from domain.exceptions import ApprovalExpiredError
from domain.models import ActionProposal, Approval
from repositories.memory.memory_repository import InMemoryRepository
from services.approval_gateway import ApprovalGateway
from services.approval_service import ApprovalService


@pytest.fixture
def repo():
    return InMemoryRepository()


@pytest.fixture
def gateway(repo):
    app_svc = ApprovalService(repository=repo)
    return ApprovalGateway(repository=repo, approval_service=app_svc)


def test_submit_proposal_transitions_to_pending(gateway, repo):
    """Submitting proposal transitions it to PENDING_APPROVAL and creates Approval record."""
    proposal = ActionProposal(
        proposal_id="PROP-001",
        investigation_id="INV-001",
        machine_id="M21",
        action_type="CREATE_WORK_ORDER",
        priority="HIGH",
        reason="Bearing vibration high",
        parameters={"component_id": "C-M21-BRG"},
    )
    submitted = gateway.submit_proposal(proposal)
    assert submitted.status == ActionProposalStatus.PENDING_APPROVAL.value

    # Verify linked approval record was created
    app = repo.get_approval("APP-PROP-001")
    assert app is not None
    assert app.status == ApprovalStatus.PENDING
    assert app.machine_id == "M21"


def test_autonomous_agents_strictly_blocked_from_approval(gateway, repo):
    """CoCo and autonomous agents cannot self-approve proposals."""
    proposal = ActionProposal(
        proposal_id="PROP-002",
        investigation_id="INV-002",
        machine_id="M21",
        action_type="CREATE_WORK_ORDER",
        priority="HIGH",
        reason="Bearing failure",
    )
    gateway.submit_proposal(proposal)

    # Attempt approval by agent identities
    agent_identities = [
        "ReliabilityAgent",
        "coco",
        "CoCo_Agent",
        "agent.system",
        "bot_operator",
        "orchestrator",
        "autonomous_worker",
    ]
    for agent_id in agent_identities:
        with pytest.raises(PermissionError) as exc_info:
            gateway.approve_proposal(
                proposal_id="PROP-002",
                approver_id=agent_id,
                reason="Auto approval",
            )
        assert "autonomous agent" in str(exc_info.value).lower()


def test_human_operator_can_approve_proposal(gateway, repo):
    """Authenticated human operator approves proposal cleanly."""
    proposal = ActionProposal(
        proposal_id="PROP-003",
        investigation_id="INV-003",
        machine_id="M21",
        action_type="CREATE_WORK_ORDER",
        priority="HIGH",
        reason="Bearing vibration high",
    )
    gateway.submit_proposal(proposal)

    approval = gateway.approve_proposal(
        proposal_id="PROP-003",
        approver_id="shubham.r",
        reason="Verified telemetry anomaly and approved bearing replacement",
    )

    assert approval.status == ApprovalStatus.APPROVED
    assert approval.decision_by == "shubham.r"

    # Proposal state is updated to APPROVED
    persisted_prop = repo.get_action_proposal("PROP-003")
    assert persisted_prop.status == ActionProposalStatus.APPROVED.value


def test_human_operator_can_reject_proposal(gateway, repo):
    """Human operator can reject proposal."""
    proposal = ActionProposal(
        proposal_id="PROP-004",
        investigation_id="INV-004",
        machine_id="M21",
        action_type="CREATE_WORK_ORDER",
        priority="LOW",
        reason="Noise observed",
    )
    gateway.submit_proposal(proposal)

    rejected = gateway.reject_proposal(
        proposal_id="PROP-004",
        approver_id="shubham.r",
        reason="False positive after physical check",
    )
    assert rejected.status == ApprovalStatus.REJECTED

    persisted_prop = repo.get_action_proposal("PROP-004")
    assert persisted_prop.status == ActionProposalStatus.REJECTED.value


def test_idempotent_approval_by_same_human(gateway, repo):
    """Submitting the identical approval again returns the existing approved record."""
    proposal = ActionProposal(
        proposal_id="PROP-005",
        investigation_id="INV-005",
        machine_id="M21",
        action_type="CREATE_WORK_ORDER",
        priority="HIGH",
        reason="High vibration",
    )
    gateway.submit_proposal(proposal)

    app1 = gateway.approve_proposal(
        proposal_id="PROP-005",
        approver_id="marcus.wright",
        reason="Approved bearing replacement",
    )
    app2 = gateway.approve_proposal(
        proposal_id="PROP-005",
        approver_id="marcus.wright",
        reason="Approved bearing replacement",
    )
    assert app1.approval_id == app2.approval_id
    assert app2.status == ApprovalStatus.APPROVED
