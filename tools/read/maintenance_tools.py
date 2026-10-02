"""Typed read tools for equipment maintenance history and failure recurrence patterns."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from domain.models import WorkOrder, MaintenanceEvent
from tools.read.base import BaseReadTool


class WorkOrderSummaryItem(BaseModel):
    work_order_id: str
    machine_id: str
    component_id: Optional[str] = None
    work_type: str = "CORRECTIVE"
    failure_code: Optional[str] = None
    status: str = "CLOSED"
    opened_ts: Optional[datetime] = None
    closed_ts: Optional[datetime] = None
    technician: Optional[str] = None
    labor_hours: float = 0.0
    parts_cost: float = 0.0
    total_cost: float = 0.0
    description: str = ""


class GetMaintenanceHistoryInput(BaseModel):
    machine_id: str = Field(..., description="Target machine ID, e.g. 'M21'")
    component_id: Optional[str] = Field(default=None, description="Optional component ID, e.g. 'C-M21-BRG'")
    lookback_days: int = Field(default=365, ge=1, le=1000, description="Lookback window in days")


class MaintenanceHistoryOutput(BaseModel):
    machine_id: str
    count: int
    work_orders: List[WorkOrderSummaryItem] = Field(default_factory=list)


class GetMaintenanceHistoryTool(BaseReadTool):
    name = "get_maintenance_history"
    description = "Retrieve logged maintenance work orders, inspections, failure codes, and repair costs for a machine."
    scope = "maintenance:read"
    input_schema = GetMaintenanceHistoryInput
    output_schema = MaintenanceHistoryOutput

    def _run(self, params: GetMaintenanceHistoryInput) -> MaintenanceHistoryOutput:
        wos = self.repo.list_work_orders(machine_id=params.machine_id)
        if params.component_id:
            wos = [w for w in wos if w.component_id == params.component_id]

        cutoff = datetime.now(timezone.utc) - timedelta(days=params.lookback_days)
        items: List[WorkOrderSummaryItem] = []
        for w in wos:
            if w.created_at and w.created_at.replace(tzinfo=timezone.utc) < cutoff:
                continue

            labor_hrs = getattr(w, "labor_hours", 0.0) or 0.0
            parts_c = getattr(w, "parts_cost", 0.0) or 0.0
            total_c = getattr(w, "total_cost", 0.0) or (parts_c + labor_hrs * 500.0)

            # Support canonical WorkOrder (failure_mode, assigned_to) and legacy (type, assigned_technician_id)
            if hasattr(w, "failure_mode") and w.failure_mode:
                work_type = w.failure_mode.value if hasattr(w.failure_mode, "value") else str(w.failure_mode)
            elif hasattr(w, "type") and w.type:
                work_type = w.type.value if hasattr(w.type, "value") else str(w.type)
            else:
                work_type = "CORRECTIVE"

            technician = getattr(w, "assigned_to", None) or getattr(w, "assigned_technician_id", None)
            status_val = w.status.value if hasattr(w.status, "value") else str(w.status)

            items.append(
                WorkOrderSummaryItem(
                    work_order_id=w.work_order_id,
                    machine_id=w.machine_id,
                    component_id=w.component_id,
                    work_type=work_type,
                    failure_code=getattr(w, "failure_code", None),
                    status=status_val,
                    opened_ts=w.created_at,
                    closed_ts=w.completed_at,
                    technician=technician,
                    labor_hours=labor_hrs,
                    parts_cost=parts_c,
                    total_cost=total_c,
                    description=w.description or "",
                )
            )

        return MaintenanceHistoryOutput(
            machine_id=params.machine_id,
            count=len(items),
            work_orders=items,
        )


class GetHistoricalFailuresInput(BaseModel):
    machine_id: str = Field(..., description="Target machine ID, e.g. 'M21'")
    component_id: Optional[str] = Field(default=None, description="Optional component ID, e.g. 'C-M21-BRG'")
    failure_code: Optional[str] = Field(default=None, description="Optional failure code filter, e.g. 'BD-BRG'")


class HistoricalFailuresOutput(BaseModel):
    machine_id: str
    component_id: Optional[str] = None
    failure_count: int
    last_failure_date: Optional[datetime] = None
    failure_codes_summary: Dict[str, int] = Field(default_factory=dict)
    recurrence_pattern: Optional[str] = None
    historical_work_orders: List[str] = Field(default_factory=list)


class GetHistoricalFailuresTool(BaseReadTool):
    name = "get_historical_failures"
    description = "Retrieve summarized historical equipment failures, recurrence intervals, and root causes."
    scope = "reliability:read"
    input_schema = GetHistoricalFailuresInput
    output_schema = HistoricalFailuresOutput

    def _run(self, params: GetHistoricalFailuresInput) -> HistoricalFailuresOutput:
        wos = self.repo.list_work_orders(machine_id=params.machine_id)
        if params.component_id:
            wos = [w for w in wos if w.component_id == params.component_id]

        code_filter = params.failure_code.upper() if params.failure_code else None

        matched_wos = []
        codes_count: Dict[str, int] = {}
        last_dt = None

        for w in wos:
            fcode = getattr(w, "failure_code", None)
            if not fcode and w.description:
                if "bearing" in w.description.lower() or "brg" in w.description.lower():
                    fcode = "BD-BRG"
                elif "motor" in w.description.lower():
                    fcode = "BD-MTR"

            if not fcode:
                continue

            if code_filter and code_filter not in fcode.upper():
                continue

            matched_wos.append(w.work_order_id)
            codes_count[fcode] = codes_count.get(fcode, 0) + 1
            if w.completed_at:
                if last_dt is None or w.completed_at > last_dt:
                    last_dt = w.completed_at
            elif w.created_at:
                if last_dt is None or w.created_at > last_dt:
                    last_dt = w.created_at

        # Check failures repository as well
        failures = self.repo.get_failure_history(params.machine_id)
        for f in failures:
            fcode = f.failure_mode.value if hasattr(f.failure_mode, "value") else str(f.failure_mode)
            if code_filter and code_filter not in fcode.upper():
                continue
            codes_count[fcode] = codes_count.get(fcode, 0) + 1
            f_ts = getattr(f, "occurred_at", None) or getattr(f, "timestamp", None)
            if f_ts:
                if last_dt is None or f_ts > last_dt:
                    last_dt = f_ts

        count = len(matched_wos) + len(failures)
        recurrence = None
        if count >= 2:
            recurrence = f"Recurrent failure pattern detected ({count} logged events)"
        elif count == 1:
            recurrence = "Single previous logged occurrence"
        else:
            recurrence = "No prior recorded failures for this component"

        return HistoricalFailuresOutput(
            machine_id=params.machine_id,
            component_id=params.component_id,
            failure_count=count,
            last_failure_date=last_dt,
            failure_codes_summary=codes_count,
            recurrence_pattern=recurrence,
            historical_work_orders=matched_wos,
        )
