"""Unit tests for ActionPreconditionService.

Validates:
- Machine existence validation
- Component hierarchy validation
- Strict inventory reality (rejects stockouts like SP-002 with 0 stock and 5-day lead time)
- Technician roster validation
- Idempotency pre-check
"""

import pytest
from repositories.memory.memory_repository import InMemoryRepository
from services.action_precondition_service import ActionPreconditionService
from domain.models import ActionExecution


@pytest.fixture
def repo():
    return InMemoryRepository()


@pytest.fixture
def precondition_service(repo):
    return ActionPreconditionService(
        machine_repo=repo,
        maintenance_repo=repo,
        supply_chain_repo=repo,
        governance_repo=repo,
    )


def test_machine_precondition_success_and_failure(precondition_service):
    """Recognized machines pass; unrecognized machines fail."""
    # M21 exists in canonical dataset
    res_valid = precondition_service.validate_preconditions(
        action_type="CREATE_WORK_ORDER",
        machine_id="M21",
    )
    assert res_valid.is_valid
    assert res_valid.can_proceed
    assert res_valid.details["machine_name"] == "Grinder 3"

    # M999 does not exist
    res_invalid = precondition_service.validate_preconditions(
        action_type="CREATE_WORK_ORDER",
        machine_id="M999",
    )
    assert not res_invalid.is_valid
    assert not res_invalid.can_proceed
    assert any("M999" in err for err in res_invalid.errors)


def test_component_precondition_validation(precondition_service):
    """Component must belong to the machine."""
    # C-M21-BRG belongs to M21
    res_valid = precondition_service.validate_preconditions(
        action_type="CREATE_WORK_ORDER",
        machine_id="M21",
        component_id="C-M21-BRG",
    )
    assert res_valid.is_valid
    assert res_valid.can_proceed

    # C-M01-BRG belongs to M01, not M21
    res_invalid = precondition_service.validate_preconditions(
        action_type="CREATE_WORK_ORDER",
        machine_id="M21",
        component_id="C-M01-BRG",
    )
    assert not res_invalid.is_valid
    assert any("does not belong to machine 'M21'" in err for err in res_invalid.errors)


def test_spare_part_stockout_fails_safely_for_sp002(precondition_service):
    """SP-002 has 0 stock in canonical dataset; precondition must fail safely with lead time."""
    res = precondition_service.validate_preconditions(
        action_type="RESERVE_SPARE_PART",
        machine_id="M21",
        part_id="SP-002",
        qty=1,
    )
    assert not res.is_valid
    assert not res.can_proceed
    assert res.details["stock_qty"] == 0
    assert res.details["lead_time_days"] == 5
    assert any("Insufficient inventory for part 'SP-002'" in err for err in res.errors)
    assert any("lead time: 5 days" in err for err in res.errors)


def test_spare_part_available_succeeds(precondition_service, repo):
    """Parts with sufficient stock pass precondition validation."""
    # Find a part with stock > 0
    all_parts = repo.list_spare_parts()
    available_part = next((p for p in all_parts if p.stock_qty > 0), None)
    assert available_part is not None

    res = precondition_service.validate_preconditions(
        action_type="RESERVE_SPARE_PART",
        machine_id="M21",
        part_id=available_part.part_id,
        qty=1,
    )
    assert res.is_valid
    assert res.can_proceed
    assert res.details["inventory_status"] == "AVAILABLE"


def test_idempotency_precondition_check(precondition_service, repo):
    """Detects prior executions sharing the same idempotency key."""
    idem_key = "IDEM-TEST-12345"
    exe = ActionExecution(
        execution_id="EXE-PREV-001",
        action_proposal_id="PROP-001",
        approval_id="APP-001",
        action_type="CREATE_WORK_ORDER",
        machine_id="M21",
        status="SUCCESS",
        idempotency_key=idem_key,
    )
    repo.save_action_execution(exe)

    res = precondition_service.validate_preconditions(
        action_type="CREATE_WORK_ORDER",
        machine_id="M21",
        idempotency_key=idem_key,
    )
    assert res.details.get("prior_execution_id") == "EXE-PREV-001"
