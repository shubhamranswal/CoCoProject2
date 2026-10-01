"""Work Order service managing creation, state transitions, completion, and idempotency.

Follows AGENT.md & architecture/architecture.md:
- Governed work order lifecycle: APPROVED -> OPEN -> ASSIGNED -> IN_PROGRESS -> COMPLETED -> VERIFIED
- Enforces state transition validation (rejects invalid state jumps)
- Enforces idempotency via idempotency_key
- Records completed maintenance events linked to work orders
- Distinguishes technician completion from verification
- Emits audit events into GovernanceRepository
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from domain.enums import FailureMode, Priority, WorkOrderStatus
from domain.exceptions import InvalidWorkOrderTransitionError
from domain.models import AuditEvent, MaintenanceEvent, WorkOrder
from repositories.base import GovernanceRepository, MaintenanceRepository

VALID_STATUS_TRANSITIONS: Dict[WorkOrderStatus, Set[WorkOrderStatus]] = {
    WorkOrderStatus.DRAFT: {WorkOrderStatus.PENDING_APPROVAL, WorkOrderStatus.CANCELLED},
    WorkOrderStatus.PENDING_APPROVAL: {WorkOrderStatus.APPROVED, WorkOrderStatus.CANCELLED},
    WorkOrderStatus.APPROVED: {WorkOrderStatus.OPEN, WorkOrderStatus.ASSIGNED, WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.CANCELLED},
    WorkOrderStatus.OPEN: {WorkOrderStatus.ASSIGNED, WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.CANCELLED},
    WorkOrderStatus.ASSIGNED: {WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.CANCELLED},
    WorkOrderStatus.IN_PROGRESS: {WorkOrderStatus.COMPLETED, WorkOrderStatus.CANCELLED},
    WorkOrderStatus.COMPLETED: {WorkOrderStatus.VERIFIED},
    WorkOrderStatus.VERIFIED: set(),
    WorkOrderStatus.CANCELLED: set(),
}


class WorkOrderService:
    """Service governing maintenance work order lifecycle and execution records."""

    def __init__(
        self,
        repository: MaintenanceRepository,
        governance_repo: Optional[GovernanceRepository] = None,
    ) -> None:
        self.repo = repository
        self.gov_repo = governance_repo

    def create_work_order(self, work_order: WorkOrder) -> WorkOrder:
        """Create a new work order with strict idempotency and audit logging."""
        if work_order.idempotency_key:
            existing_orders = self.repo.list_work_orders(machine_id=work_order.machine_id)
            for existing in existing_orders:
                if existing.idempotency_key == work_order.idempotency_key:
                    self._log_audit(
                        actor=work_order.created_by or "SYSTEM",
                        action_type="WORK_ORDER_IDEMPOTENT_REPLAY",
                        resource_id=existing.work_order_id,
                        details={
                            "idempotency_key": work_order.idempotency_key,
                            "existing_status": existing.status.value,
                        },
                    )
                    return existing

        created = self.repo.create_work_order(work_order)
        self._log_audit(
            actor=work_order.created_by or "SYSTEM",
            action_type="WORK_ORDER_CREATED",
            resource_id=created.work_order_id,
            details={
                "machine_id": created.machine_id,
                "component_id": created.component_id,
                "priority": created.priority.value if hasattr(created.priority, "value") else str(created.priority),
                "failure_mode": created.failure_mode.value if hasattr(created.failure_mode, "value") else str(created.failure_mode),
                "approval_id": created.source_approval_id,
                "idempotency_key": created.idempotency_key,
            },
        )
        return created

    def get_work_order(self, work_order_id: str) -> Optional[WorkOrder]:
        """Retrieve work order by ID."""
        return self.repo.get_work_order(work_order_id)

    def list_work_orders(
        self, machine_id: Optional[str] = None, status: Optional[WorkOrderStatus] = None
    ) -> List[WorkOrder]:
        """List work orders filtered by machine and/or status."""
        return self.repo.list_work_orders(machine_id=machine_id, status=status)

    def transition_status(
        self,
        work_order_id: str,
        new_status: WorkOrderStatus,
        actor: str = "SYSTEM",
        notes: str = "",
    ) -> WorkOrder:
        """Transition work order status through the governed state machine."""
        wo = self.repo.get_work_order(work_order_id)
        if not wo:
            raise ValueError(f"Work order '{work_order_id}' not found.")

        if wo.status == new_status:
            return wo

        allowed = VALID_STATUS_TRANSITIONS.get(wo.status, set())
        if new_status not in allowed:
            raise InvalidWorkOrderTransitionError(
                f"Invalid work order status transition from {wo.status.value} to {new_status.value}. "
                f"Allowed transitions from {wo.status.value}: {[s.value for s in allowed]}",
                entity_id=work_order_id,
            )

        updated = self.repo.update_work_order_status(work_order_id, new_status)
        self._log_audit(
            actor=actor,
            action_type="WORK_ORDER_STATUS_CHANGED",
            resource_id=work_order_id,
            details={
                "previous_status": wo.status.value,
                "new_status": new_status.value,
                "notes": notes,
            },
        )
        return updated

    def complete_work_order(
        self,
        work_order_id: str,
        technician_name: str,
        duration_hours: float,
        notes: str,
        actions_performed: Optional[List[str]] = None,
        failure_mode: Optional[FailureMode] = None,
    ) -> Tuple[WorkOrder, MaintenanceEvent]:
        """Complete maintenance work order and record physical maintenance event.

        Note: Work order completion represents physical execution by the technician.
        It does NOT equal verification. Verification is determined strictly by post-maintenance
        sensor telemetry and calculated by VerificationService.
        """
        wo = self.repo.get_work_order(work_order_id)
        if not wo:
            raise ValueError(f"Work order '{work_order_id}' not found.")

        now = datetime.now(timezone.utc)
        # Advance status if needed (from OPEN / ASSIGNED to IN_PROGRESS, then COMPLETED)
        if wo.status in (WorkOrderStatus.APPROVED, WorkOrderStatus.OPEN, WorkOrderStatus.ASSIGNED):
            wo = self.transition_status(work_order_id, WorkOrderStatus.IN_PROGRESS, actor=technician_name)

        if wo.status != WorkOrderStatus.IN_PROGRESS and wo.status != WorkOrderStatus.COMPLETED:
            raise ValueError(f"Cannot complete work order in status {wo.status.value}.")

        updated_wo = wo.model_copy(
            update={
                "status": WorkOrderStatus.COMPLETED,
                "completed_at": now,
            }
        )
        if hasattr(self.repo, "update_work_order"):
            self.repo.update_work_order(updated_wo)
        else:
            self.repo.update_work_order_status(work_order_id, WorkOrderStatus.COMPLETED)

        # Create physical maintenance event
        maintenance_event = MaintenanceEvent(
            maintenance_id=f"MAINT-{work_order_id}-{int(now.timestamp())}",
            work_order_id=work_order_id,
            machine_id=wo.machine_id,
            component_id=wo.component_id,
            maintenance_type="CORRECTIVE",
            performed_at=now,
            technician_name=technician_name,
            duration_hours=duration_hours,
            notes=notes,
            failure_mode=failure_mode or wo.failure_mode,
            actions_performed=actions_performed or [],
        )
        self.repo.save_maintenance_event(maintenance_event)

        self._log_audit(
            actor=technician_name,
            action_type="WORK_ORDER_COMPLETED",
            resource_id=work_order_id,
            details={
                "maintenance_id": maintenance_event.maintenance_id,
                "machine_id": wo.machine_id,
                "duration_hours": duration_hours,
                "notes": notes,
                "actions_performed": actions_performed or [],
            },
        )
        return updated_wo, maintenance_event

    def verify_work_order(self, work_order_id: str, verifier: str = "SYSTEM") -> WorkOrder:
        """Mark work order as VERIFIED following successful post-maintenance verification."""
        wo = self.repo.get_work_order(work_order_id)
        if not wo:
            raise ValueError(f"Work order '{work_order_id}' not found.")

        if wo.status != WorkOrderStatus.COMPLETED:
            raise ValueError(
                f"Work order '{work_order_id}' cannot be verified: current status is {wo.status.value} (must be COMPLETED)."
            )

        updated = self.transition_status(
            work_order_id,
            WorkOrderStatus.VERIFIED,
            actor=verifier,
            notes="Physical sensor verification passed nominal thresholds.",
        )
        return updated

    def _log_audit(self, actor: str, action_type: str, resource_id: str, details: Dict[str, Any]) -> None:
        if self.gov_repo and hasattr(self.gov_repo, "log_audit"):
            event = AuditEvent(
                audit_id=f"AUD-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
                actor=actor,
                action_type=action_type,
                resource_id=resource_id,
                resource_type="WORK_ORDER",
                details=details,
            )
            self.gov_repo.log_audit(event)
