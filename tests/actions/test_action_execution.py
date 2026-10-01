"""Unit tests for ActionExecutionService and zero-trust execution pipeline.

Validates:
- Execution requires explicit approved status
- Autonomous agents cannot execute unapproved proposals
- Precondition failure (such as SP-002 stockout) produces safe failure without state corruption
- Valid execution creates work order or reserves inventory and records ActionExecution
- Duplicate execution with idempotency key returns cached original result
"""

import pytest

from domain.enums import ActionProposalStatus, ApprovalStatus
from domain.exceptions import ApprovalRequiredError
from domain.models import ActionProposal, Approval
from repositories.memory.memory_repository import InMemoryRepository
from services.action_execution_service import ActionExecutionService
from services.action_precondition_service import ActionPreconditionService
from services.approval_service import ApprovalService
from services.work_order_service import WorkOrderService
from tools.actions.action_registry import create_m5_action_registry


@pytest.fixture
def execution_env():
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
    exec_svc = ActionExecutionService(
        governance_repo=repo,
        action_registry=action_reg,
        precondition_service=precondition_svc,
        approval_service=app_svc,
    )
    return repo, app_svc, exec_svc


def test_unapproved_proposal_execution_is_blocked(execution_env):
    """Attempting to execute an unapproved or proposed proposal raises ApprovalRequiredError."""
    repo, app_svc, exec_svc = execution_env

    prop = ActionProposal(
        proposal_id="PROP-UNAPPROVED",
        investigation_id="INV-001",
        machine_id="M21",
        action_type="CREATE_WORK_ORDER",
        priority="HIGH",
        reason="Bearing issue",
        status=ActionProposalStatus.PROPOSED.value,
    )
    repo.save_action_proposal(prop)

    with pytest.raises(ApprovalRequiredError):
        exec_svc.execute_proposal(
            proposal_id="PROP-UNAPPROVED",
            caller_actor="sarah.chen",
        )


def test_successful_work_order_execution_after_human_approval(execution_env):
    """Approved proposal executes, creates work order, records ActionExecution, and updates proposal."""
    repo, app_svc, exec_svc = execution_env

    # 1. Create and save proposal
    prop = ActionProposal(
        proposal_id="PROP-WO-1",
        investigation_id="INV-WO-1",
        machine_id="M21",
        action_type="CREATE_WORK_ORDER",
        priority="HIGH",
        reason="Bearing failure imminent",
        status=ActionProposalStatus.APPROVED.value,
        parameters={
            "component_id": "C-M21-BRG",
            "title": "Replace Bearing C-M21-BRG",
            "description": "LOTO and swap bearing",
            "assigned_to": "MAINT-CREW-1",
        },
    )
    repo.save_action_proposal(prop)

    # 2. Save approved approval record
    app = Approval(
        approval_id="APP-PROP-WO-1",
        action_proposal_id="PROP-WO-1",
        investigation_id="INV-WO-1",
        machine_id="M21",
        status=ApprovalStatus.APPROVED,
        decision_by="sarah.chen",
    )
    repo.create_approval(app)

    # 3. Execute proposal
    execution = exec_svc.execute_proposal(
        proposal_id="PROP-WO-1",
        caller_actor="sarah.chen",
        idempotency_key="IDEM-WO-1",
    )

    assert execution.status == "SUCCESS"
    assert execution.action_type == "CREATE_WORK_ORDER"
    assert "work_order_id" in execution.result_data

    # Check work order exists in repo
    wo_id = execution.result_data["work_order_id"]
    wo = repo.get_work_order(wo_id)
    assert wo is not None
    assert wo.machine_id == "M21"
    assert wo.component_id == "C-M21-BRG"

    # Check proposal is updated to EXECUTED
    persisted_prop = repo.get_action_proposal("PROP-WO-1")
    assert persisted_prop.status == ActionProposalStatus.EXECUTED.value


def test_sp002_stockout_safely_fails_execution_without_crashing(execution_env):
    """Reserving SP-002 (stock=0) fails preconditions safely, marking execution as FAILED."""
    repo, app_svc, exec_svc = execution_env

    prop = ActionProposal(
        proposal_id="PROP-SP002",
        investigation_id="INV-SP002",
        machine_id="M21",
        action_type="RESERVE_SPARE_PART",
        priority="HIGH",
        reason="Need bearing for M21",
        status=ActionProposalStatus.APPROVED.value,
        parameters={
            "part_id": "SP-002",
            "qty": 1,
        },
    )
    repo.save_action_proposal(prop)

    app = Approval(
        approval_id="APP-PROP-SP002",
        action_proposal_id="PROP-SP002",
        investigation_id="INV-SP002",
        machine_id="M21",
        status=ApprovalStatus.APPROVED,
        decision_by="marcus.wright",
    )
    repo.create_approval(app)

    # Execute
    execution = exec_svc.execute_proposal(
        proposal_id="PROP-SP002",
        caller_actor="marcus.wright",
    )

    assert execution.status == "FAILED"
    assert "SP-002" in execution.error_message
    assert "lead time: 5 days" in execution.error_message

    # Proposal marked FAILED
    persisted_prop = repo.get_action_proposal("PROP-SP002")
    assert persisted_prop.status == ActionProposalStatus.FAILED.value


def test_idempotent_execution_returns_prior_result(execution_env):
    """Submitting the same execution with identical idempotency key returns the prior execution."""
    repo, app_svc, exec_svc = execution_env

    prop = ActionProposal(
        proposal_id="PROP-IDEM",
        investigation_id="INV-IDEM",
        machine_id="M21",
        action_type="CREATE_WORK_ORDER",
        priority="HIGH",
        reason="Bearing issue",
        status=ActionProposalStatus.APPROVED.value,
        parameters={
            "component_id": "C-M21-BRG",
            "title": "Replace Bearing",
            "description": "Replace bearing",
        },
    )
    repo.save_action_proposal(prop)

    app = Approval(
        approval_id="APP-PROP-IDEM",
        action_proposal_id="PROP-IDEM",
        investigation_id="INV-IDEM",
        machine_id="M21",
        status=ApprovalStatus.APPROVED,
        decision_by="sarah.chen",
    )
    repo.create_approval(app)

    # First execution
    exec1 = exec_svc.execute_proposal(
        proposal_id="PROP-IDEM",
        caller_actor="sarah.chen",
        idempotency_key="IDEM-STABLE-KEY-999",
    )
    assert exec1.status == "SUCCESS"

    # Second execution with same idempotency key
    # Proposal will be marked EXECUTED, but even if called again or with same key:
    # First re-allow status if needed or check existing
    exec2 = exec_svc.execute_proposal(
        proposal_id="PROP-IDEM",
        caller_actor="sarah.chen",
        idempotency_key="IDEM-STABLE-KEY-999",
    )
    assert exec2.execution_id == exec1.execution_id
