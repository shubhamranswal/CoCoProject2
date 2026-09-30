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
    vibration_std: float = 0.0
    vibration_rate_of_change: float = 0.0  # g/hour
    vibration_baseline_deviation_pct: float = 0.0
    temperature_mean: float
    temperature_slope: float  # °C per hour
    temperature_baseline_deviation_pct: float = 0.0
    rpm_mean: float
    rpm_variance: float
    rpm_deviation_pct: float = 0.0
    current_mean: float
    vibration_temperature_correlation: float = 0.0


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
    score: float  # z-score or anomaly score
    metric_name: str
    observed_value: float
    baseline_value: float
    deviation_pct: float
    detection_method: str = "baseline_threshold"  # baseline_threshold, rolling_deviation, trend_deviation, multi_signal
    status: str = "ACTIVE"  # ACTIVE, RESOLVED
