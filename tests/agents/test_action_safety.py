"""Action safety and governed authorization tests.

Follows AGENT.md & architecture/architecture.md:
- Autonomous agents strictly prohibited from self-approving actions
- Action tools require explicit approval record in repository with status APPROVED
- Client-supplied approval parameters (e.g. approved=True) are rejected
- Expired or rejected approvals cannot be executed
- Machine ID mismatch rejected
- Idempotent action execution
"""

from datetime import datetime, timedelta, timezone
import pytest

from domain.enums import ApprovalStatus, FailureMode, Priority, WorkOrderStatus
from domain.models import Approval, WorkOrder
from repositories.memory.memory_repository import InMemoryRepository
from services.approval_service import ApprovalService
from services.work_order_service import WorkOrderService
from tools.actions.work_order_actions import CreateWorkOrderAction


@pytest.fixture
def test_setup():
    repo = InMemoryRepository()
    app_svc = ApprovalService(repository=repo)
    wo_svc = WorkOrderService(repository=repo, governance_repo=repo)
    action_tool = CreateWorkOrderAction(
        approval_service=app_svc,
        work_order_service=wo_svc,
        governance_repo=repo,
    )
    return repo, app_svc, wo_svc, action_tool


def test_agent_cannot_self_approve(test_setup):
    """Verify autonomous agents cannot approve actions."""
    repo, app_svc, wo_svc, action_tool = test_setup
    app = Approval(
        approval_id="APP-TEST-001",
        investigation_id="INV-001",
        machine_id="M204",
        status=ApprovalStatus.PENDING,
    )
    app_svc.request_approval(app)

    disallowed_agents = [
        "ReliabilityAgent",
        "reliabilityagent-v1",
        "AutonomousBot",
        "SystemAgent",
        "Agent-LLM",
    ]

    for agent_id in disallowed_agents:
        with pytest.raises(PermissionError) as exc_info:
            app_svc.approve_action(app.approval_id, agent_id, reason="Self-approving")
        assert "autonomous agent" in str(exc_info.value).lower()


def test_human_operator_can_approve(test_setup):
    """Verify authenticated human operators can approve actions."""
    repo, app_svc, wo_svc, action_tool = test_setup
    app = Approval(
        approval_id="APP-TEST-002",
        investigation_id="INV-002",
        machine_id="M204",
        status=ApprovalStatus.PENDING,
    )
    app_svc.request_approval(app)

    approved = app_svc.approve_action(app.approval_id, "operator.john", reason="Reviewed physical telemetry")
    assert approved.status == ApprovalStatus.APPROVED
    assert approved.decision_by == "operator.john"
    assert approved.decision_reason == "Reviewed physical telemetry"


def test_action_requires_approved_status(test_setup):
    """Action executor must reject unapproved or pending approval."""
    repo, app_svc, wo_svc, action_tool = test_setup
    app = Approval(
        approval_id="APP-TEST-003",
        investigation_id="INV-003",
        machine_id="M204",
        status=ApprovalStatus.PENDING,
    )
    app_svc.request_approval(app)

    with pytest.raises(PermissionError) as exc:
        action_tool.execute(
            caller_actor="operator.john",
            approval_id=app.approval_id,
            machine_id="M204",
            component_id="COMP-M204-BRG-DE",
            title="Replace bearing",
            description="Replace worn bearing",
        )
    assert "must be 'approved'" in str(exc.value).lower()


def test_client_spoofed_approval_rejected(test_setup):
    """Caller supplying approved=True or bypass flags is strictly rejected."""
    repo, app_svc, wo_svc, action_tool = test_setup
    with pytest.raises(PermissionError) as exc:
        action_tool.execute(
            caller_actor="attacker",
            approval_id="APP-NONEXISTENT",
            machine_id="M204",
            component_id="COMP-M204-BRG-DE",
            title="Replace bearing",
            description="Bypassing approval",
            approved=True,
        )
    assert "client-supplied approval parameters are forbidden" in str(exc.value).lower()


def test_expired_approval_rejected(test_setup):
    """Action executor rejects expired approvals."""
    repo, app_svc, wo_svc, action_tool = test_setup
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    app = Approval(
        approval_id="APP-TEST-004",
        investigation_id="INV-004",
        machine_id="M204",
        status=ApprovalStatus.APPROVED,
        decision_by="operator.sarah",
        expires_at=past,
    )
    repo._approvals[app.approval_id] = app

    with pytest.raises(ValueError) as exc:
        action_tool.execute(
            caller_actor="operator.sarah",
            approval_id=app.approval_id,
            machine_id="M204",
            component_id="COMP-M204-BRG-DE",
            title="Replace bearing",
            description="Executing after expiration",
        )
    assert "expired" in str(exc.value).lower()


def test_rejected_approval_cannot_be_executed(test_setup):
    """Rejected approval cannot create work order."""
    repo, app_svc, wo_svc, action_tool = test_setup
    app = Approval(
        approval_id="APP-TEST-005",
        investigation_id="INV-005",
        machine_id="M204",
        status=ApprovalStatus.PENDING,
    )
    app_svc.request_approval(app)
    app_svc.reject_action(app.approval_id, "manager.alice", reason="Too close to planned downtime window")

    with pytest.raises(PermissionError) as exc:
        action_tool.execute(
            caller_actor="manager.alice",
            approval_id=app.approval_id,
            machine_id="M204",
            component_id="COMP-M204-BRG-DE",
            title="Replace bearing",
            description="Executing rejected action",
        )
    assert "must be 'approved'" in str(exc.value).lower()


def test_machine_mismatch_rejected(test_setup):
    """Action executor rejects approval intended for a different machine."""
    repo, app_svc, wo_svc, action_tool = test_setup
    app = Approval(
        approval_id="APP-TEST-006",
        investigation_id="INV-006",
        machine_id="M204",
        status=ApprovalStatus.PENDING,
    )
    app_svc.request_approval(app)
    app_svc.approve_action(app.approval_id, "operator.john", reason="Approved for M204")

    with pytest.raises(ValueError) as exc:
        action_tool.execute(
            caller_actor="operator.john",
            approval_id=app.approval_id,
            machine_id="M101",  # Mismatch!
            component_id="COMP-M101-BRG",
            title="Replace bearing",
            description="Executing for wrong machine",
        )
    assert "does not match" in str(exc.value).lower()


def test_idempotent_duplicate_action(test_setup):
    """Duplicate work order creation with same idempotency key returns existing work order."""
    repo, app_svc, wo_svc, action_tool = test_setup
    app = Approval(
        approval_id="APP-TEST-007",
        investigation_id="INV-007",
        machine_id="M204",
        status=ApprovalStatus.PENDING,
    )
    app_svc.request_approval(app)
    app_svc.approve_action(app.approval_id, "operator.john", reason="Approved")

    wo1 = action_tool.execute(
        caller_actor="operator.john",
        approval_id=app.approval_id,
        machine_id="M204",
        component_id="COMP-M204-BRG-DE",
        title="Replace bearing",
        description="Replace worn bearing",
        idempotency_key="IDEM-TEST-007",
    )

    wo2 = action_tool.execute(
        caller_actor="operator.john",
        approval_id=app.approval_id,
        machine_id="M204",
        component_id="COMP-M204-BRG-DE",
        title="Replace bearing",
        description="Replace worn bearing",
        idempotency_key="IDEM-TEST-007",
    )

    assert wo1.work_order_id == wo2.work_order_id
    assert len(wo_svc.list_work_orders(machine_id="M204")) == 1
