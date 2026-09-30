"""Read tools for telemetry, feature vectors, anomalies, and failure risk."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field

from domain.models import Anomaly, FailureRisk, FeatureVector, TelemetryMeasurement
from tools.read.base import BaseReadTool


class GetRecentTelemetryInput(BaseModel):
    machine_id: str = Field(..., description="Target machine ID, e.g. 'M204'")
    sensor_id: Optional[str] = Field(default=None, description="Optional sensor filter, e.g. 'SEN-M204-VIB'")
    metric: Optional[str] = Field(default=None, description="Optional metric substring filter")
    hours: int = Field(default=24, ge=1, le=168, description="Lookback window in hours (bounded between 1 and 168)")
    limit: int = Field(default=100, ge=1, le=500, description="Max measurements to return (bounded between 1 and 500)")


class TelemetryListOutput(BaseModel):
    machine_id: str
    count: int
    measurements: List[TelemetryMeasurement] = Field(default_factory=list)


class GetRecentTelemetryTool(BaseReadTool):
    name = "get_recent_telemetry"
    description = "Retrieve bounded recent telemetry measurements for a machine or specific sensor."
    scope = "telemetry:read"
    input_schema = GetRecentTelemetryInput
    output_schema = TelemetryListOutput

    def _run(self, params: GetRecentTelemetryInput) -> TelemetryListOutput:
        measurements = self.repo.get_recent_measurements(
            machine_id=params.machine_id,
            sensor_id=params.sensor_id,
            limit=params.limit,
        )
        if params.metric:
            q = params.metric.upper()
            measurements = [m for m in measurements if q in m.sensor_id.upper() or q in m.unit.upper()]

        return TelemetryListOutput(
            machine_id=params.machine_id,
            count=len(measurements),
            measurements=measurements,
        )


class GetTelemetryFeaturesInput(BaseModel):
    machine_id: str = Field(..., description="Target machine ID")


class FeatureVectorOutput(BaseModel):
    machine_id: str
    features: Optional[FeatureVector] = None


class GetTelemetryFeaturesTool(BaseReadTool):
    name = "get_telemetry_features"
    description = "Retrieve the latest engineered feature vector (RMS, peak, slope, correlation) for a machine."
    scope = "telemetry:read"
    input_schema = GetTelemetryFeaturesInput
    output_schema = FeatureVectorOutput

    def _run(self, params: GetTelemetryFeaturesInput) -> FeatureVectorOutput:
        fv = self.repo.get_latest_features(params.machine_id)
        return FeatureVectorOutput(machine_id=params.machine_id, features=fv)


class GetActiveAnomaliesInput(BaseModel):
    machine_id: str = Field(..., description="Target machine ID")
    active_only: bool = Field(default=True, description="Whether to filter for active anomalies only")


class AnomalyListOutput(BaseModel):
    machine_id: str
    count: int
    anomalies: List[Anomaly] = Field(default_factory=list)


class GetActiveAnomaliesTool(BaseReadTool):
    name = "get_active_anomalies"
    description = "Retrieve detected statistical and multi-signal anomalies for a machine."
    scope = "telemetry:read"
    input_schema = GetActiveAnomaliesInput
    output_schema = AnomalyListOutput

    def _run(self, params: GetActiveAnomaliesInput) -> AnomalyListOutput:
        anomalies = self.repo.get_anomalies(machine_id=params.machine_id, active_only=params.active_only)
        return AnomalyListOutput(
            machine_id=params.machine_id,
            count=len(anomalies),
            anomalies=anomalies,
        )


class GetFailureRiskInput(BaseModel):
    machine_id: str = Field(..., description="Target machine ID")


class FailureRiskOutput(BaseModel):
    machine_id: str
    failure_risk: Optional[FailureRisk] = None


class GetFailureRiskTool(BaseReadTool):
    name = "get_failure_risk"
    description = "Retrieve the latest deterministic failure risk prediction and factor breakdown for a machine."
    scope = "reliability:read"
    input_schema = GetFailureRiskInput
    output_schema = FailureRiskOutput

    def _run(self, params: GetFailureRiskInput) -> FailureRiskOutput:
        risk = self.repo.get_latest_failure_risk(params.machine_id)
        return FailureRiskOutput(machine_id=params.machine_id, failure_risk=risk)
