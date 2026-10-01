"""Data Freshness and Ingestion Timing domain models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class DataFreshness(BaseModel):
    """Operational data freshness indicator distinguishing event, ingestion, and processing times."""

    source_type: str = "TELEMETRY"
    machine_id: str = "M204"
    last_event_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ingestion_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processing_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    age_seconds: float = 0.0
    is_simulated: bool = True
    status: str = "HEALTHY"

    @property
    def display_age(self) -> str:
        if self.is_simulated:
            return f"{self.age_seconds:.1f}s (Simulated)"
        return f"{self.age_seconds:.1f}s"
