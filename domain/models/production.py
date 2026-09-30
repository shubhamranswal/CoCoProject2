"""Production and Downtime domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ProductionRun(BaseModel):
    run_id: str
    line_id: str
    machine_id: str
    product_code: str
    start_time: datetime
    end_time: Optional[datetime] = None
    planned_units: int
    actual_units: int
    good_units: int
    scrap_units: int
    ideal_cycle_time_seconds: float = 3.6  # 1000 units/hour
    status: str = "COMPLETED"


class DowntimeEvent(BaseModel):
    downtime_id: str
    machine_id: str
    line_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_minutes: float
    reason_code: str
    category: str = "UNPLANNED"  # UNPLANNED, PLANNED, CHANGEOVER
    description: str = ""
