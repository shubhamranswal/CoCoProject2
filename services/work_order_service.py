"""Work Order service managing creation, updates, and idempotency."""

from __future__ import annotations

from typing import List, Optional

from domain.enums import WorkOrderStatus
from domain.models import WorkOrder
from repositories.base import MaintenanceRepository


class WorkOrderService:
    def __init__(self, repository: MaintenanceRepository) -> None:
        self.repo = repository

    def create_work_order(self, work_order: WorkOrder) -> WorkOrder:
        return self.repo.create_work_order(work_order)

    def get_work_order(self, work_order_id: str) -> Optional[WorkOrder]:
        return self.repo.get_work_order(work_order_id)

    def list_work_orders(
        self, machine_id: Optional[str] = None, status: Optional[WorkOrderStatus] = None
    ) -> List[WorkOrder]:
        return self.repo.list_work_orders(machine_id=machine_id, status=status)

    def complete_work_order(self, work_order_id: str) -> WorkOrder:
        return self.repo.update_work_order_status(work_order_id, WorkOrderStatus.COMPLETED)
