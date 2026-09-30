"""Telemetry, Feature, Baseline, and Anomaly domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from domain.enums import Severity


class TelemetryMeasurement(BaseModel):
    measurement_id: str
    machine_id: str
    sensor_id: str
    timestamp: datetime
    value: float
    unit: str
    quality: str = "VALID"  # VALID, SUSPECT, OUT_OF_RANGE


class FeatureVector(BaseModel):
    feature_id: str
    machine_id: str
    timestamp: datetime
    window_minutes: int = 15
    vibration_rms: float
    vibration_peak: float
    temperature_mean: float
    temperature_slope: float  # °C per hour
    rpm_mean: float
    rpm_variance: float
    current_mean: float


class Baseline(BaseModel):
    baseline_id: str
    machine_id: str
    signal_name: str
    operating_regime: str = "NORMAL_LOAD"
    baseline_mean: float
    baseline_std: float
    warning_threshold: float
    critical_threshold: float
    unit: str


class Anomaly(BaseModel):
    anomaly_id: str
    machine_id: str
    sensor_id: str
    detected_at: datetime
    severity: Severity
    score: float  # z-score or probability (e.g. 3.2)
    metric_name: str
    observed_value: float
    baseline_value: float
    deviation_pct: float
    status: str = "ACTIVE"  # ACTIVE, RESOLVED
