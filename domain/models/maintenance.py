"""Maintenance and Work Order domain models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field

from domain.enums import FailureMode, Priority, WorkOrderStatus


class MaintenanceEvent(BaseModel):
    maintenance_id: str
    machine_id: str
    component_id: Optional[str] = None
    maintenance_type: str  # INSPECTION, REPLACEMENT, LUBRICATION, REPAIR
    performed_at: datetime
    technician_name: str
    duration_hours: float
    parts_replaced: List[str] = Field(default_factory=list)
    notes: str = ""


class WorkOrder(BaseModel):
    work_order_id: str
    machine_id: str
    component_id: Optional[str] = None
    investigation_id: Optional[str] = None
    recommendation_id: Optional[str] = None
    title: str
    description: str
    failure_mode: FailureMode
    priority: Priority
    status: WorkOrderStatus = WorkOrderStatus.DRAFT
    assigned_to: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    scheduled_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    checklist: List[str] = Field(default_factory=list)
    idempotency_key: Optional[str] = None
