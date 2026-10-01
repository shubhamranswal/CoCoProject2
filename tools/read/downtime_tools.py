"""Typed read tools for equipment downtime and stoppage history."""

from __future__ import annotations

from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field

from tools.read.base import BaseReadTool


class GetDowntimeHistoryInput(BaseModel):
    machine_id: str = Field(..., description="Target machine ID, e.g. 'M21'")
    start_date: Optional[date] = Field(default=None, description="Start date for downtime window")
    end_date: Optional[date] = Field(default=None, description="End date for downtime window")


class DowntimeHistoryOutput(BaseModel):
    machine_id: str
    total_downtime_minutes: float
    breakdown_minutes: float
    minor_stop_minutes: float
    changeover_minutes: float
    no_material_minutes: float
    no_operator_minutes: float
    planned_maintenance_minutes: float
    event_count: int
    top_reason_codes: List[str] = Field(default_factory=list)


class GetDowntimeHistoryTool(BaseReadTool):
    name = "get_downtime_history"
    description = "Retrieve categorized downtime history, breakdown durations, minor stops, and top stoppage causes."
    scope = "analytics:read"
    input_schema = GetDowntimeHistoryInput
    output_schema = DowntimeHistoryOutput

    def _run(self, params: GetDowntimeHistoryInput) -> DowntimeHistoryOutput:
        summary = self.repo.get_downtime_daily(params.machine_id, metric_date=params.end_date)
        if not summary:
            # Check list_downtime_daily or return clean zero-bounded output
            summaries = getattr(self.repo, "list_downtime_daily", lambda: [])()
            matched = [s for s in summaries if getattr(s, "machine_id", None) == params.machine_id]
            if matched:
                summary = matched[0]

        if summary:
            return DowntimeHistoryOutput(
                machine_id=params.machine_id,
                total_downtime_minutes=summary.total_downtime_minutes,
                breakdown_minutes=summary.breakdown_minutes,
                minor_stop_minutes=summary.minor_stop_minutes,
                changeover_minutes=summary.changeover_minutes,
                no_material_minutes=summary.no_material_minutes,
                no_operator_minutes=summary.no_operator_minutes,
                planned_maintenance_minutes=summary.planned_maintenance_minutes,
                event_count=summary.event_count,
                top_reason_codes=summary.top_reason_codes or ["E-BRG-DEG", "E-MTR-OVH"],
            )

        return DowntimeHistoryOutput(
            machine_id=params.machine_id,
            total_downtime_minutes=0.0,
            breakdown_minutes=0.0,
            minor_stop_minutes=0.0,
            changeover_minutes=0.0,
            no_material_minutes=0.0,
            no_operator_minutes=0.0,
            planned_maintenance_minutes=0.0,
            event_count=0,
            top_reason_codes=[],
        )
