"""Read tools for machine hierarchy, components, and health assessment context."""

from __future__ import annotations

from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field

from domain.models import Component, Machine, Sensor, MachineHealthDaily
from tools.read.base import BaseReadTool


class GetMachineContextInput(BaseModel):
    machine_id: str = Field(..., description="Unique machine identifier, e.g. 'M21'")


class MachineContextOutput(BaseModel):
    machine: Optional[Machine] = None
    components: List[Component] = Field(default_factory=list)
    sensors: List[Sensor] = Field(default_factory=list)
    line_name: Optional[str] = None
    plant_name: Optional[str] = None


class GetMachineContextTool(BaseReadTool):
    name = "get_machine_context"
    description = "Retrieve physical asset hierarchy, components, calibrated sensors, and status for a machine."
    scope = "asset:read"
    input_schema = GetMachineContextInput
    output_schema = MachineContextOutput

    def _run(self, params: GetMachineContextInput) -> MachineContextOutput:
        mach = self.repo.get_machine(params.machine_id)
        if not mach:
            return MachineContextOutput()

        comps = self.repo.get_components(params.machine_id)
        sensors = self.repo.get_sensors(params.machine_id)

        line_name = None
        plant_name = None
        plant = self.repo.get_plant("PLT01") or self.repo.get_plant("PLANT-01")
        if plant:
            plant_name = plant.name
            for line in self.repo.list_lines(plant.plant_id):
                if line.line_id == mach.line_id:
                    line_name = line.name
                    break

        return MachineContextOutput(
            machine=mach,
            components=comps,
            sensors=sensors,
            line_name=line_name,
            plant_name=plant_name,
        )


class GetMachineHealthInput(BaseModel):
    machine_id: str = Field(..., description="Target machine ID, e.g. 'M21'")
    metric_date: Optional[date] = Field(default=None, description="Optional target date")


class MachineHealthOutput(BaseModel):
    machine_id: str
    machine_name: str
    health_status: str
    health_score: float
    state: str
    active_anomalies_count: int
    open_alerts_count: int
    latest_prediction_prob: Optional[float] = None
    risk_level: Optional[str] = None
    downtime_hours_7d: float = 0.0


class GetMachineHealthTool(BaseReadTool):
    name = "get_machine_health"
    description = "Retrieve machine health score, operational state, anomaly counts, and risk tier."
    scope = "analytics:read"
    input_schema = GetMachineHealthInput
    output_schema = MachineHealthOutput

    def _run(self, params: GetMachineHealthInput) -> MachineHealthOutput:
        mach = self.repo.get_machine(params.machine_id)
        mach_name = mach.name if mach else params.machine_id
        state_str = mach.state.value if mach and hasattr(mach.state, "value") else "RUNNING"

        # Check analytics repository
        mhd = self.repo.get_machine_health_daily(params.machine_id, metric_date=params.metric_date)
        if mhd:
            # Deterministically derive health_score from latest_failure_prob or health_status
            if mhd.latest_failure_prob is not None:
                derived_score = round(max(0.0, min(100.0, (1.0 - mhd.latest_failure_prob) * 100.0)), 1)
            elif mhd.health_status == "CRITICAL":
                derived_score = 15.0
            elif mhd.health_status in ("WARNING", "DEGRADING"):
                derived_score = 60.0
            else:
                derived_score = 100.0

            dt_hours = round(mhd.downtime_minutes / 60.0, 2) if mhd.downtime_minutes else 0.0

            return MachineHealthOutput(
                machine_id=params.machine_id,
                machine_name=mach_name,
                health_status=mhd.health_status,
                health_score=derived_score,
                state=state_str,
                active_anomalies_count=mhd.exceedance_count,
                open_alerts_count=mhd.open_alerts,
                latest_prediction_prob=mhd.latest_failure_prob,
                risk_level=mhd.latest_risk_level or ("CRITICAL" if mhd.health_status == "CRITICAL" else "LOW"),
                downtime_hours_7d=dt_hours,
            )

        # Fallback to direct repository lookups
        anomalies = self.repo.get_anomalies(params.machine_id)
        alerts = self.repo.list_alerts(machine_id=params.machine_id)
        open_alerts = [a for a in alerts if getattr(a, "status", None) and str(a.status).upper() not in ("RESOLVED", "DISMISSED")]

        latest_pred = self.repo.get_latest_prediction(params.machine_id)
        pred_prob = latest_pred.failure_probability if latest_pred else None
        risk_lvl = "LOW"
        if pred_prob:
            if pred_prob >= 0.85:
                risk_lvl = "CRITICAL"
            elif pred_prob >= 0.70:
                risk_lvl = "HIGH"
            elif pred_prob >= 0.40:
                risk_lvl = "MEDIUM"

        health_sc = 95.0
        health_st = "HEALTHY"
        if risk_lvl == "CRITICAL":
            health_sc = 25.0
            health_st = "CRITICAL"
        elif risk_lvl == "HIGH":
            health_sc = 50.0
            health_st = "DEGRADING"

        dt_summary = getattr(self.repo, "get_downtime_daily", lambda m: None)(params.machine_id)
        dt_hours = round(getattr(dt_summary, "total_downtime_minutes", 0.0) / 60.0, 2) if dt_summary else 0.0

        return MachineHealthOutput(
            machine_id=params.machine_id,
            machine_name=mach_name,
            health_status=health_st,
            health_score=health_sc,
            state=state_str,
            active_anomalies_count=len(anomalies),
            open_alerts_count=len(open_alerts),
            latest_prediction_prob=pred_prob,
            risk_level=risk_lvl,
            downtime_hours_7d=dt_hours,
        )
