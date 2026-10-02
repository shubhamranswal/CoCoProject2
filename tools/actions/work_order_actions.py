"""Governed Work Order action tools.

Follows AGENT.md & architecture/architecture.md:
- Requires approved Human Approval record in repository
- Rejects unapproved, expired, or mismatched machines
- Strictly rejects client-side bypass attempts
- Idempotent work order generation
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field

from domain.enums import FailureMode, Priority, WorkOrderStatus
from domain.models import WorkOrder
from repositories.base import GovernanceRepository
from services.approval_service import ApprovalService
from services.work_order_service import WorkOrderService
from tools.actions.base import BaseActionTool


class CreateWorkOrderInput(BaseModel):
    """Input payload for governed work order creation."""

    approval_id: str = Field(description="Repository approval ID granting authorization")
    machine_id: str = Field(description="Target machine ID")
    component_id: str = Field(description="Target component ID")
    title: str = Field(description="Title of the work order")
    description: str = Field(description="Actionable maintenance instructions")
    priority: Priority = Field(default=Priority.HIGH, description="Work order priority")
    failure_mode: FailureMode = Field(default=FailureMode.BEARING_DEGRADATION, description="Target failure mode")
    assigned_to: Optional[str] = Field(default=None, description="Assigned technician or maintenance team")
    scheduled_date: Optional[datetime] = Field(default=None, description="Scheduled execution timestamp")
    investigation_id: Optional[str] = Field(default=None, description="Linked investigation ID")
    recommendation_id: Optional[str] = Field(default=None, description="Linked recommendation ID")
    checklist: List[str] = Field(default_factory=list, description="Inspection or task checklist")
    idempotency_key: Optional[str] = Field(default=None, description="Unique client key ensuring idempotent execution")


class CreateWorkOrderAction(BaseActionTool):
    """Governed action tool to create maintenance work orders upon authorized approval."""

    name: str = "create_work_order"
    description: str = "Create a maintenance work order in FACTORY_MAINTENANCE following verified human approval."
    input_schema = CreateWorkOrderInput
    output_schema = WorkOrder

    def __init__(
        self,
        approval_service: ApprovalService,
        work_order_service: WorkOrderService,
        governance_repo: Optional[GovernanceRepository] = None,
    ) -> None:
        super().__init__(approval_service=approval_service, governance_repo=governance_repo)
        self.work_order_service = work_order_service

    def _run(self, params: CreateWorkOrderInput, caller_actor: str) -> WorkOrder:
        """Create work order and link it to the approved recommendation and investigation."""
        now = datetime.now(timezone.utc)
        work_order_id = f"WO-{params.machine_id}-{int(now.timestamp())}"

        # If idempotency key was not explicitly provided, derive a stable one from approval_id
        idem_key = params.idempotency_key or f"IDEM-{params.approval_id}"

        work_order = WorkOrder(
            work_order_id=work_order_id,
            machine_id=params.machine_id,
            component_id=params.component_id,
            investigation_id=params.investigation_id,
            recommendation_id=params.recommendation_id,
            source_approval_id=params.approval_id,
            created_by=caller_actor,
            title=params.title,
            description=params.description,
            failure_mode=params.failure_mode,
            priority=params.priority,
            status=WorkOrderStatus.APPROVED,
            assigned_to=params.assigned_to,
            created_at=now,
            scheduled_date=params.scheduled_date,
            checklist=getattr(params, "checklist", []) or [],
            idempotency_key=idem_key,
        )

        return self.work_order_service.create_work_order(work_order)
