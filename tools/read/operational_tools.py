"""Read tools for alerts, failure history, maintenance history, work orders, and OEE."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field

from domain.enums import WorkOrderStatus
from domain.models import Alert, Failure, MaintenanceEvent, WorkOrder
from tools.read.base import BaseReadTool


class GetAlertContextInput(BaseModel):
    alert_id: str = Field(..., description="Target alert ID, e.g. 'ALT-M204-...'")


class AlertContextOutput(BaseModel):
    alert: Optional[Alert] = None


class GetAlertContextTool(BaseReadTool):
    name = "get_alert_context"
    description = "Retrieve details and trigger context for a specific reliability alert."
    scope = "investigation:read"
    input_schema = GetAlertContextInput
    output_schema = AlertContextOutput

    def _run(self, params: GetAlertContextInput) -> AlertContextOutput:
        alert = self.repo.get_alert(params.alert_id)
        return AlertContextOutput(alert=alert)


class GetFailureHistoryInput(BaseModel):
    machine_id: str = Field(..., description="Target machine ID")
    failure_mode: Optional[str] = Field(default=None, description="Optional failure mode filter")


class FailureHistoryOutput(BaseModel):
    machine_id: str
    count: int
    failures: List[Failure] = Field(default_factory=list)


class GetFailureHistoryTool(BaseReadTool):
    name = "get_failure_history"
    description = "Retrieve historical recorded equipment failures and root cause analyses."
    scope = "reliability:read"
    input_schema = GetFailureHistoryInput
    output_schema = FailureHistoryOutput

    def _run(self, params: GetFailureHistoryInput) -> FailureHistoryOutput:
        failures = self.repo.get_failure_history(params.machine_id)
        if params.failure_mode:
            q = params.failure_mode.upper()
            failures = [f for f in failures if q in f.failure_mode.value.upper() or q in f.root_cause.upper()]

        return FailureHistoryOutput(
            machine_id=params.machine_id,
            count=len(failures),
            failures=failures,
        )


class GetMaintenanceHistoryInput(BaseModel):
    machine_id: str = Field(..., description="Target machine ID")
    limit: int = Field(default=20, ge=1, le=100, description="Max maintenance records to return")


class MaintenanceHistoryOutput(BaseModel):
    machine_id: str
    count: int
    events: List[MaintenanceEvent] = Field(default_factory=list)


class GetMaintenanceHistoryTool(BaseReadTool):
    name = "get_maintenance_history"
    description = "Retrieve logged maintenance, inspection, and repair events for a machine."
    scope = "maintenance:read"
    input_schema = GetMaintenanceHistoryInput
    output_schema = MaintenanceHistoryOutput

    def _run(self, params: GetMaintenanceHistoryInput) -> MaintenanceHistoryOutput:
        events = self.repo.get_maintenance_history(params.machine_id, limit=params.limit)
        return MaintenanceHistoryOutput(
            machine_id=params.machine_id,
            count=len(events),
            events=events,
        )


class GetOpenWorkOrdersInput(BaseModel):
    machine_id: str = Field(..., description="Target machine ID")


class OpenWorkOrdersOutput(BaseModel):
    machine_id: str
    count: int
    work_orders: List[WorkOrder] = Field(default_factory=list)


class GetOpenWorkOrdersTool(BaseReadTool):
    name = "get_open_work_orders"
    description = "Retrieve currently active or scheduled maintenance work orders to avoid duplicate actions."
    scope = "maintenance:read"
    input_schema = GetOpenWorkOrdersInput
    output_schema = OpenWorkOrdersOutput

    def _run(self, params: GetOpenWorkOrdersInput) -> OpenWorkOrdersOutput:
        all_wos = self.repo.list_work_orders(machine_id=params.machine_id)
        open_wos = [
            wo for wo in all_wos
            if wo.status in (WorkOrderStatus.DRAFT, WorkOrderStatus.PENDING_APPROVAL, WorkOrderStatus.APPROVED, WorkOrderStatus.SCHEDULED, WorkOrderStatus.IN_PROGRESS)
        ]
        return OpenWorkOrdersOutput(
            machine_id=params.machine_id,
            count=len(open_wos),
            work_orders=open_wos,
        )


class GetOEEImpactInput(BaseModel):
    machine_id: str = Field(..., description="Target machine ID")


class OEEImpactOutput(BaseModel):
    machine_id: str
    line_id: Optional[str] = None
    oee: float = 1.0
    availability: float = 1.0
    performance: float = 1.0
    quality: float = 1.0
    downtime_minutes: float = 0.0
    is_impacted: bool = False
    details: str = ""


class GetOEEImpactTool(BaseReadTool):
    name = "get_oee_impact"
    description = "Retrieve current line operational effectiveness (OEE) and downtime impact caused by machine condition."
    scope = "production:read"
    input_schema = GetOEEImpactInput
    output_schema = OEEImpactOutput

    def _run(self, params: GetOEEImpactInput) -> OEEImpactOutput:
        mach = self.repo.get_machine(params.machine_id)
        line_id = mach.line_id if mach else None

        # Check latest risk and anomalies to report operational impact
        risk = self.repo.get_latest_failure_risk(params.machine_id)
        anomalies = self.repo.get_anomalies(params.machine_id, active_only=True)

        if risk and risk.risk_score >= 0.80:
            return OEEImpactOutput(
                machine_id=params.machine_id,
                line_id=line_id,
                oee=0.593,
                availability=0.6875,
                performance=0.914,
                quality=0.949,
                downtime_minutes=75.0,
                is_impacted=True,
                details="Line B experiencing emergency shutdown / severe speed loss due to critical bearing overheating",
            )
        elif risk and risk.risk_score >= 0.50:
            return OEEImpactOutput(
                machine_id=params.machine_id,
                line_id=line_id,
                oee=0.828,
                availability=0.9625,
                performance=0.884,
                quality=0.975,
                downtime_minutes=18.0,
                is_impacted=True,
                details="Line B micro-stops and motor de-rating due to vibration warning threshold breach",
            )
        else:
            return OEEImpactOutput(
                machine_id=params.machine_id,
                line_id=line_id,
                oee=0.995,
                availability=1.0,
                performance=1.0,
                quality=0.995,
                downtime_minutes=0.0,
                is_impacted=False,
                details="Normal nominal throughput",
            )
