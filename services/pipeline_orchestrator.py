"""Single deterministic intelligence pipeline orchestrator.

Follows AGENT.md:
- Orchestrates: Telemetry -> Features -> Baseline -> Anomaly -> Failure Risk -> Alert -> OEE
- Persists all intermediate intelligence artifacts through repository layer
- Yields structured PipelineExecutionResult ready for future agent investigations
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from domain.enums import FailureMode, HealthStatus
from domain.models import (
    Alert,
    Anomaly,
    Baseline,
    DowntimeEvent,
    FailureRisk,
    FeatureVector,
    ProductionRun,
    TelemetryMeasurement,
)
from ml.features.feature_extractor import FeatureExtractor
from ml.inference.risk_scorer import FailureRiskScorer
from repositories.base import (
    InvestigationRepository,
    MachineRepository,
    MaintenanceRepository,
    ReliabilityRepository,
    TelemetryRepository,
)
from repositories import get_repository
from services.alert_service import AlertService
from services.anomaly_service import AnomalyService
from services.oee_service import OEEResult, OEEService
from services.reliability_service import ReliabilityService


@dataclass
class PipelineExecutionResult:
    machine_id: str
    timestamp: datetime
    measurements_count: int
    features: FeatureVector
    anomalies: List[Anomaly]
    failure_risk: FailureRisk
    alert: Optional[Alert]
    oee: Optional[OEEResult]
    machine_health: HealthStatus


class PipelineOrchestrator:
    def __init__(
        self,
        repository: Any = None,
        feature_extractor: Optional[FeatureExtractor] = None,
        anomaly_service: Optional[AnomalyService] = None,
        reliability_service: Optional[ReliabilityService] = None,
        alert_service: Optional[AlertService] = None,
        oee_service: Optional[OEEService] = None,
    ) -> None:
        self.repo = repository or get_repository()
        self.extractor = feature_extractor or FeatureExtractor()
        self.anomaly_svc = anomaly_service or AnomalyService(self.repo)
        self.rel_svc = reliability_service or ReliabilityService(
            reliability_repo=self.repo,
            machine_repo=self.repo,
            maintenance_repo=self.repo,
        )
        self.alert_svc = alert_service or AlertService(self.repo)
        self.oee_svc = oee_service or OEEService()

    def run_reliability_pipeline(
        self,
        machine_id: str,
        measurements: List[TelemetryMeasurement],
        production_run: Optional[ProductionRun] = None,
        downtime_events: Optional[List[DowntimeEvent]] = None,
        failure_mode: FailureMode = FailureMode.BEARING_DEGRADATION,
    ) -> PipelineExecutionResult:
        """Execute the end-to-end deterministic intelligence pipeline."""
        if not measurements:
            raise ValueError(f"Cannot run reliability pipeline for {machine_id} with empty measurements")

        # 1. Ingest telemetry measurements
        self.repo.save_measurements(measurements)

        # 2. Extract Baselines
        baselines: Dict[str, Baseline] = {}
        for sig in ("vibration_rms", "temperature", "rpm", "current"):
            b = self.repo.get_baseline(machine_id, sig)
            if b:
                baselines[sig] = b

        # 3. Calculate Features
        features = self.extractor.extract_features(
            machine_id=machine_id,
            measurements=measurements,
            baselines=baselines,
            timestamp=measurements[-1].timestamp,
        )
        self.repo.save_feature(features)

        # 4. Compare to baseline & Detect Anomalies
        anomalies = self.anomaly_svc.detect_anomalies(features=features, baselines=baselines)

        # 5. Calculate Failure Risk & update Health Assessment
        risk = self.rel_svc.evaluate_failure_risk(
            machine_id=machine_id,
            features=features,
            active_anomalies=anomalies,
            failure_mode=failure_mode,
        )

        # 6. Generate / Update Correlated Alert
        alert = self.alert_svc.evaluate_risk_for_alert(risk)

        # 7. Calculate Operational Impact / OEE
        oee_res: Optional[OEEResult] = None
        if production_run:
            oee_res = self.oee_svc.calculate_oee(
                production_run=production_run,
                downtime_events=downtime_events,
            )

        # 8. Retrieve latest machine state
        mach = self.repo.get_machine(machine_id)
        current_health = mach.health_status if mach else HealthStatus.UNKNOWN

        return PipelineExecutionResult(
            machine_id=machine_id,
            timestamp=features.timestamp,
            measurements_count=len(measurements),
            features=features,
            anomalies=anomalies,
            failure_risk=risk,
            alert=alert,
            oee=oee_res,
            machine_health=current_health,
        )
