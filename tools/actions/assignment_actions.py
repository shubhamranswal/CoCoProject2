"""Governed Technician Assignment action tools.

Follows Milestone 5 Zero-Trust Architecture:
- Requires approved Human Approval record in repository
- Assigns authorized technician to existing work order
- Fully audited and idempotent
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

from domain.enums import WorkOrderStatus
from repositories.base import GovernanceRepository, MaintenanceRepository
from services.approval_service import ApprovalService
from tools.actions.base import BaseActionTool


class AssignTechnicianInput(BaseModel):
    """Input payload for governed technician assignment."""

    approval_id: str = Field(description="Repository approval ID granting authorization")
    machine_id: str = Field(description="Target machine ID")
    work_order_id: str = Field(description="Target work order ID")
    technician_id: str = Field(description="Target technician identifier or name")
    idempotency_key: Optional[str] = Field(default=None, description="Unique client key ensuring idempotent execution")


class AssignTechnicianResult(BaseModel):
    """Result of technician assignment request."""

    success: bool
    work_order_id: str
    assigned_to: str
    status: str
    message: str


class AssignTechnicianAction(BaseActionTool):
    """Governed action tool to assign a technician to an approved work order."""

    name: str = "assign_technician"
    description: str = "Assign an authorized technician to a work order following human approval."
    input_schema = AssignTechnicianInput
    output_schema = AssignTechnicianResult

    def __init__(
        self,
        approval_service: ApprovalService,
        maintenance_repo: MaintenanceRepository,
        governance_repo: Optional[GovernanceRepository] = None,
    ) -> None:
        super().__init__(approval_service=approval_service, governance_repo=governance_repo)
        self.maintenance_repo = maintenance_repo

    def _run(self, params: AssignTechnicianInput, caller_actor: str) -> AssignTechnicianResult:
        """Assign technician to work order and update status if needed."""
        wo = self.maintenance_repo.get_work_order(params.work_order_id)
        if not wo:
            return AssignTechnicianResult(
                success=False,
                work_order_id=params.work_order_id,
                assigned_to=params.technician_id,
                status="NOT_FOUND",
                message=f"Work order '{params.work_order_id}' not found.",
            )

        updated_wo = wo.model_copy(
            update={
                "assigned_to": params.technician_id,
                "status": WorkOrderStatus.ASSIGNED if wo.status == WorkOrderStatus.APPROVED else wo.status,
            }
        )
        self.maintenance_repo.update_work_order(updated_wo)

        return AssignTechnicianResult(
            success=True,
            work_order_id=params.work_order_id,
            assigned_to=params.technician_id,
            status="ASSIGNED",
            message=f"Work order '{params.work_order_id}' assigned to technician '{params.technician_id}'.",
        )
