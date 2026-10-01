"""Reliability, Failure, and Risk domain models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List, Dict
from pydantic import BaseModel, Field

from domain.enums import FailureMode, HealthStatus, RiskLevel, Severity


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
    risk_level: RiskLevel = RiskLevel.LOW

    prediction_horizon_hours: int = 72
    model_version: str = "v1.2.0-deterministic-weighted"
    prediction_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    contributing_factors: Dict[str, float] = Field(default_factory=dict)
    contributing_signals: List[str] = Field(default_factory=list)


class HealthAssessment(BaseModel):
    assessment_id: str
    machine_id: str
    health_status: HealthStatus
    health_score: float = Field(..., ge=0.0, le=100.0)
    primary_concern: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MLFailurePrediction(BaseModel):
    """Predictive ML model output for component failure probability."""

    prediction_id: str
    machine_id: str
    component_id: Optional[str] = None
    failure_mode: FailureMode = FailureMode.BEARING_DEGRADATION
    failure_probability: float = Field(..., ge=0.0, le=1.0)
    prediction_horizon_hours: int = 24
    model_name: str = "BearingFailure-v1.0"
    model_version: str = "1.0.0"
    training_dataset_version: str = "v2026.03"
    feature_schema_version: str = "v1.0"
    confidence: float = Field(default=0.88, ge=0.0, le=1.0)
    threshold_exceeded: bool = False
    top_contributing_features: Dict[str, float] = Field(default_factory=dict)
    feature_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    prediction_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PredictionOutcome(BaseModel):
    """Auditable feedback record closing the predictive learning loop."""

    outcome_id: str
    prediction_id: str
    machine_id: str
    predicted_failure: bool
    actual_failure: bool
    prediction_horizon_hours: int = 24
    lead_time_hours: Optional[float] = None
    verification_id: Optional[str] = None
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_correct: bool
    notes: Optional[str] = None
