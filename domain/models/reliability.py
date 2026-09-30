"""Reliability, Failure, and Risk domain models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field

from domain.enums import FailureMode, HealthStatus, Severity


class Failure(BaseModel):
    failure_id: str
    machine_id: str
    component_id: Optional[str] = None
    failure_mode: FailureMode
    occurred_at: datetime
    root_cause: str
    downtime_hours: float
    maintenance_action_taken: str
    resolved_at: Optional[datetime] = None


class FailureRisk(BaseModel):
    risk_id: str
    machine_id: str
    failure_mode: FailureMode
    risk_score: float = Field(..., ge=0.0, le=1.0)
    prediction_horizon_hours: int = 72
    model_version: str = "v1.2.0-bearing-xgb"
    prediction_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    contributing_signals: List[str] = Field(default_factory=list)


class HealthAssessment(BaseModel):
    assessment_id: str
    machine_id: str
    health_status: HealthStatus
    health_score: float = Field(..., ge=0.0, le=100.0)
    primary_concern: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
