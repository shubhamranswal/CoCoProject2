"""Production Hardening, Snowflake Parity, and Operational Governance Tests.

Follows Phase 15-17 requirements:
- Repository parity between InMemoryRepository and SnowflakeRepository
- Strict Snowflake error policy (RepositoryUnavailableError, no silent fallback)
- Persistent operational state (not dependent on Streamlit session state)
- Work order state machine validation and InvalidWorkOrderTransitionError
- Physical verification prerequisites and VerificationNotReadyError
- Action idempotency and audit trail
- Autonomous agent authorization safety and ApprovalExpiredError
- Controlled demo reset and M204 lifecycle stage machine
"""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
import pytest

from app.streamlit.services.view_service import CommandCenterFacade
from domain.enums import (
    AlertStatus,
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
    CommandCenterError,
    InvalidMachineError,
    InvalidWorkOrderTransitionError,
    RepositoryUnavailableError,
    VerificationNotReadyError,
)
from domain.models import Approval, WorkOrder
from repositories import get_repository
from repositories.base import (
    GovernanceRepository,
    InvestigationRepository,
    KnowledgeRepository,
    MachineRepository,
    MaintenanceRepository,
    ReliabilityRepository,
    TelemetryRepository,
)
from repositories.memory.memory_repository import InMemoryRepository
from repositories.snowflake.snowflake_repository import SnowflakeRepository
from services.approval_service import ApprovalService
from services.verification_service import VerificationService
from services.work_order_service import WorkOrderService
from tools.actions.work_order_actions import CreateWorkOrderAction


# =============================================================================
# 1. REPOSITORY PARITY TESTS
# =============================================================================
def test_repository_interface_parity():
    """Verify InMemoryRepository and SnowflakeRepository implement all base methods."""
    abstract_interfaces = [
        MachineRepository,
        TelemetryRepository,
        MaintenanceRepository,
        ReliabilityRepository,
        InvestigationRepository,
        GovernanceRepository,
        KnowledgeRepository,
    ]

    for iface in abstract_interfaces:
        methods = [
            m for m in dir(iface)
            if not m.startswith("_") and callable(getattr(iface, m))
        ]
        for method_name in methods:
            # InMemory must implement
            assert hasattr(InMemoryRepository, method_name), (
                f"InMemoryRepository missing method {method_name} from {iface.__name__}"
            )
            # Snowflake must implement
            assert hasattr(SnowflakeRepository, method_name), (
                f"SnowflakeRepository missing method {method_name} from {iface.__name__}"
            )

            # Compare parameter signatures
            in_mem_sig = inspect.signature(getattr(InMemoryRepository, method_name))
            snow_sig = inspect.signature(getattr(SnowflakeRepository, method_name))

            in_mem_params = list(in_mem_sig.parameters.keys())
            snow_params = list(snow_sig.parameters.keys())
            assert in_mem_params == snow_params, (
                f"Signature mismatch for {method_name}: InMemory={in_mem_params} vs Snowflake={snow_params}"
            )


# =============================================================================
# 2. STRICT SNOWFLAKE ERROR POLICY (NO SILENT FALLBACK)
# =============================================================================
def test_snowflake_strict_error_policy():
    """Verify selecting Snowflake with missing/invalid credentials raises RepositoryUnavailableError."""
    # When Snowflake is unconfigured or fails connection test, get_repository('snowflake') MUST raise
    try:
        repo = get_repository(backend="snowflake")
        # If Snowflake happens to be configured in environment, it should be a SnowflakeRepository
        assert isinstance(repo, SnowflakeRepository)
    except RepositoryUnavailableError as exc:
        # Expected when credentials unconfigured or connection fails
        assert isinstance(exc, CommandCenterError)
        assert isinstance(exc, RuntimeError)
        assert "Snowflake" in str(exc) or "credentials" in str(exc).lower()


# =============================================================================
# 3. OPERATIONAL STATE PERSISTENCE ACROSS SESSIONS
# =============================================================================
def test_operational_state_persistence():
    """Verify mutations persist directly in the repository and are readable by separate instances."""
    repo = InMemoryRepository()
    app_svc = ApprovalService(repository=repo)
    wo_svc = WorkOrderService(repository=repo, governance_repo=repo)
    action_tool = CreateWorkOrderAction(approval_service=app_svc, work_order_service=wo_svc, governance_repo=repo)

    # Create and approve an approval
    app = Approval(
        approval_id="APP-PERSIST-001",
        investigation_id="INV-PERSIST-001",
        machine_id="M204",
        status=ApprovalStatus.PENDING,
    )
    repo.create_approval(app)
    app_svc.approve_action("APP-PERSIST-001", "operator.shubham", "Approved bearing replacement")

    # Execute action to create work order
    wo = action_tool.execute(
        caller_actor="operator.shubham",
        approval_id="APP-PERSIST-001",
        machine_id="M204",
        component_id="COMP-M204-BRG-DE",
        title="Replace M204 Bearing",
        description="Replace worn bearing assembly",
    )

    # Verify state is queryable directly from repo
    fetched_wo = repo.get_work_order(wo.work_order_id)
    assert fetched_wo is not None
    assert fetched_wo.status == WorkOrderStatus.APPROVED
    assert fetched_wo.source_approval_id == "APP-PERSIST-001"

    # Verify audit event was persisted
    audits = repo.list_audit_events()
    assert any(a.resource_id == wo.work_order_id for a in audits)


# =============================================================================
# 4. ACTION IDEMPOTENCY & REPLAY AUDITING
# =============================================================================
def test_action_idempotency_and_replay():
    """Verify repeated execution with same idempotency key returns existing record and logs replay."""
    repo = InMemoryRepository()
    app_svc = ApprovalService(repository=repo)
    wo_svc = WorkOrderService(repository=repo, governance_repo=repo)

    wo1 = WorkOrder(
        work_order_id="WO-IDEM-001",
        machine_id="M204",
        component_id="COMP-M204-BRG-DE",
        title="Replace DE Bearing",
        description="First attempt",
        status=WorkOrderStatus.APPROVED,
        priority=Priority.HIGH,
        failure_mode=FailureMode.BEARING_DEGRADATION,
        idempotency_key="IDEM-STABLE-KEY-123",
        created_at=datetime.now(timezone.utc),
    )
    res1 = wo_svc.create_work_order(wo1)

    # Second call with identical idempotency key
    wo2 = WorkOrder(
        work_order_id="WO-IDEM-002",
        machine_id="M204",
        component_id="COMP-M204-BRG-DE",
        title="Replace DE Bearing Duplicate",
        description="Second attempt",
        status=WorkOrderStatus.APPROVED,
        priority=Priority.HIGH,
        failure_mode=FailureMode.BEARING_DEGRADATION,
        idempotency_key="IDEM-STABLE-KEY-123",
        created_at=datetime.now(timezone.utc),
    )
    res2 = wo_svc.create_work_order(wo2)

    # Must return original work order
    assert res1.work_order_id == res2.work_order_id == "WO-IDEM-001"

    # Must have recorded idempotent replay in audit log
    audits = repo.list_audit_events()
    replay_events = [a for a in audits if a.action_type == "WORK_ORDER_IDEMPOTENT_REPLAY"]
    assert len(replay_events) == 1
    assert replay_events[0].resource_id == "WO-IDEM-001"


# =============================================================================
# 5. GOVERNED WORK ORDER STATE MACHINE & TRANSITION ERRORS
# =============================================================================
def test_work_order_state_machine_validation():
    """Verify illegal work order transitions raise InvalidWorkOrderTransitionError."""
    repo = InMemoryRepository()
    wo_svc = WorkOrderService(repository=repo, governance_repo=repo)

    wo = WorkOrder(
        work_order_id="WO-STATE-001",
        machine_id="M204",
        component_id="COMP-M204-BRG-DE",
        title="Bearing Repair",
        description="Repair task",
        status=WorkOrderStatus.OPEN,
        priority=Priority.HIGH,
        failure_mode=FailureMode.BEARING_DEGRADATION,
        created_at=datetime.now(timezone.utc),
    )
    repo.create_work_order(wo)

    # Attempt illegal jump directly from OPEN to COMPLETED
    with pytest.raises(InvalidWorkOrderTransitionError) as exc:
        wo_svc.transition_status("WO-STATE-001", WorkOrderStatus.COMPLETED)
    assert "invalid work order status transition" in str(exc.value).lower()
    assert exc.value.entity_id == "WO-STATE-001"

    # Valid transition to IN_PROGRESS
    started = wo_svc.transition_status("WO-STATE-001", WorkOrderStatus.IN_PROGRESS, actor="tech.shubham")
    assert started.status == WorkOrderStatus.IN_PROGRESS

    # Valid transition to COMPLETED
    completed = wo_svc.transition_status("WO-STATE-001", WorkOrderStatus.COMPLETED, actor="tech.shubham")
    assert completed.status == WorkOrderStatus.COMPLETED

    # Cannot transition backward from COMPLETED to IN_PROGRESS
    with pytest.raises(InvalidWorkOrderTransitionError):
        wo_svc.transition_status("WO-STATE-001", WorkOrderStatus.IN_PROGRESS)


# =============================================================================
# 6. PHYSICAL VERIFICATION PREREQUISITE SAFETY
# =============================================================================
def test_verification_requires_completed_work_order():
    """Verify physical verification is rejected if work order is not COMPLETED."""
    facade = CommandCenterFacade(backend_mode="in_memory")
    facade.reset_demo(seed_degradation=True)

    alerts = facade.repo.list_alerts(machine_id="M204", status=AlertStatus.OPEN)
    assert len(alerts) >= 1
    inv_res = facade.run_reliability_investigation(alerts[0].alert_id)

    facade.approve_action(inv_res.approval.approval_id, "operator.shubham", "Approved repair")
    wo = facade.create_work_order_from_approval(inv_res.approval.approval_id, "operator.shubham")

    # Work order is in APPROVED status (not COMPLETED)
    assert wo.status == WorkOrderStatus.APPROVED

    # Attempting verification now must fail with VerificationNotReadyError
    with pytest.raises(VerificationNotReadyError) as exc:
        facade.run_verification(work_order_id=wo.work_order_id, verifier="inspector.elena")
    assert "must be completed" in str(exc.value).lower()
    assert exc.value.entity_id == wo.work_order_id


# =============================================================================
# 7. AUTHORIZATION SAFETY: AGENT SELF-APPROVAL & EXPIRED APPROVAL
# =============================================================================
def test_approval_safety_and_expiration():
    """Verify agents cannot approve and expired approvals cannot be executed."""
    repo = InMemoryRepository()
    app_svc = ApprovalService(repository=repo)
    wo_svc = WorkOrderService(repository=repo, governance_repo=repo)
    action_tool = CreateWorkOrderAction(approval_service=app_svc, work_order_service=wo_svc, governance_repo=repo)

    # Expired approval
    past = datetime.now(timezone.utc) - timedelta(minutes=10)
    app = Approval(
        approval_id="APP-EXP-001",
        investigation_id="INV-EXP-001",
        machine_id="M204",
        status=ApprovalStatus.PENDING,
        expires_at=past,
    )
    repo.create_approval(app)

    # Approving expired approval raises ApprovalExpiredError
    with pytest.raises(ApprovalExpiredError) as exc:
        app_svc.approve_action("APP-EXP-001", "operator.shubham", "Late approval")
    assert "expired" in str(exc.value).lower()

    # Autonomous bot cannot approve
    fresh_app = Approval(
        approval_id="APP-AGENT-001",
        investigation_id="INV-AGENT-001",
        machine_id="M204",
        status=ApprovalStatus.PENDING,
    )
    repo.create_approval(fresh_app)
    with pytest.raises(PermissionError):
        app_svc.approve_action("APP-AGENT-001", "ReliabilityAgent-Autonomous", "Self approval")


# =============================================================================
# 8. CONTROLLED DEMO RESET & STAGE EVALUATION
# =============================================================================
def test_controlled_demo_reset_and_stage_state_machine():
    """Verify reset_demo returns M204 to clean HEALTHY baseline and stage machine tracks progress."""
    facade = CommandCenterFacade(backend_mode="in_memory")

    # 1. Clean reset to healthy baseline
    facade.reset_demo(seed_degradation=False)
    m204 = facade.repo.get_machine("M204")
    assert m204.health_status == HealthStatus.HEALTHY
    alerts = facade.repo.list_alerts(machine_id="M204", status=AlertStatus.OPEN)
    assert len(alerts) == 0
    assert facade.get_current_demo_stage("M204") == "HEALTHY"

    # 2. Trigger degradation pipeline
    facade.run_m204_degradation_pipeline()
    alerts = facade.repo.list_alerts(machine_id="M204", status=AlertStatus.OPEN)
    assert len(alerts) >= 1
    assert facade.get_current_demo_stage("M204") == "ALERTED"

    # 3. Trigger Investigation Agent
    inv_res = facade.run_reliability_investigation(alerts[0].alert_id)
    assert facade.get_current_demo_stage("M204") == "INVESTIGATED"

    # 4. Human Approval
    facade.approve_action(inv_res.approval.approval_id, "lead.shubham", "Approved bearing swap")
    assert facade.get_current_demo_stage("M204") == "APPROVED"

    # 5. Create Work Order
    wo = facade.create_work_order_from_approval(inv_res.approval.approval_id, "lead.shubham")
    assert facade.get_current_demo_stage("M204") == "WORK_ORDER_CREATED"

    # 6. Start Work Order
    facade.start_work_order(wo.work_order_id, "tech.mike")
    assert facade.get_current_demo_stage("M204") == "IN_PROGRESS"

    # 7. Complete Work Order
    facade.complete_work_order(
        work_order_id=wo.work_order_id,
        technician_name="tech.mike",
        duration_hours=2.0,
        notes="SKF 6205 bearing replaced and laser aligned.",
        actions_performed=["LOTO", "bearing_swap", "alignment"],
    )
    assert facade.get_current_demo_stage("M204") == "MAINTENANCE_COMPLETED"

    # 8. Physical Verification (PASSED)
    verif = facade.run_verification(work_order_id=wo.work_order_id, verifier="elena.inspector", simulate_failure=False)
    assert verif.verification_status == VerificationStatus.VERIFIED
    assert facade.get_current_demo_stage("M204") == "VERIFIED"
