"""Deterministic OEE (Overall Equipment Effectiveness) Calculation Service.

Follows AGENT.md & architecture/architecture.md:
- OEE = Availability × Performance × Quality
- Computed strictly from production runs and downtime events
- Never computed by an LLM
- Deterministic arithmetic
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from domain.models import DowntimeEvent, ProductionRun


@dataclass(frozen=True)
class OEEResult:
    planned_time_minutes: float
    operating_time_minutes: float
    downtime_minutes: float
    planned_units: int
    actual_units: int
    good_units: int
    scrap_units: int
    ideal_cycle_time_seconds: float
    availability: float  # [0.0, 1.0]
    performance: float   # [0.0, 1.0]
    quality: float       # [0.0, 1.0]
    oee: float           # [0.0, 1.0]
    oee_pct: float       # [0.0, 100.0]


class OEEService:
    """Service providing deterministic industrial OEE calculations."""

    @staticmethod
    def calculate_oee(
        production_run: ProductionRun,
        downtime_events: Optional[List[DowntimeEvent]] = None,
    ) -> OEEResult:
        """Calculate OEE strictly from operational run numbers and recorded downtime."""
        downtimes = downtime_events or []

        # 1. Planned Production Time
        if production_run.end_time and production_run.start_time:
            delta_sec = (production_run.end_time - production_run.start_time).total_seconds()
            planned_minutes = max(1.0, delta_sec / 60.0)
        else:
            # Default to standard 8-hour shift if unclosed
            planned_minutes = 480.0

        # 2. Downtime & Operating Time
        downtime_minutes = sum(d.duration_minutes for d in downtimes)
        operating_minutes = max(0.0, planned_minutes - downtime_minutes)

        # 3. Availability
        availability = round(min(1.0, operating_minutes / planned_minutes), 4)

        # 4. Performance (Operating speed relative to rated ideal cycle time)
        operating_seconds = operating_minutes * 60.0
        if operating_seconds > 0 and production_run.actual_units > 0:
            target_time_seconds = production_run.actual_units * production_run.ideal_cycle_time_seconds
            performance = round(min(1.0, target_time_seconds / operating_seconds), 4)
        else:
            performance = 0.0

        # 5. Quality (Good units / Actual units)
        if production_run.actual_units > 0:
            quality = round(min(1.0, max(0.0, production_run.good_units / production_run.actual_units)), 4)
        else:
            quality = 1.0

        # 6. Overall OEE
        oee = round(availability * performance * quality, 4)
        oee_pct = round(oee * 100.0, 2)

        return OEEResult(
            planned_time_minutes=round(planned_minutes, 1),
            operating_time_minutes=round(operating_minutes, 1),
            downtime_minutes=round(downtime_minutes, 1),
            planned_units=production_run.planned_units,
            actual_units=production_run.actual_units,
            good_units=production_run.good_units,
            scrap_units=production_run.scrap_units,
            ideal_cycle_time_seconds=production_run.ideal_cycle_time_seconds,
            availability=availability,
            performance=performance,
            quality=quality,
            oee=oee,
            oee_pct=oee_pct,
        )
