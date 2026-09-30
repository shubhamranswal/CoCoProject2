"""Reliability service coordinating risk scoring and health assessments.

Follows AGENT.md:
- Persists failure risk predictions to FACTORY_RELIABILITY.FAILURE_RISK
- Updates machine health status in FACTORY_RELIABILITY.HEALTH_ASSESSMENT
"""

from __future__ import annotations

from typing import List, Optional

from domain.enums import FailureMode, HealthStatus, MachineState
from domain.models import Anomaly, FailureRisk, FeatureVector, HealthAssessment
from ml.inference.risk_scorer import FailureRiskScorer, RiskScoringConfig
from repositories.base import MachineRepository, MaintenanceRepository, ReliabilityRepository


class ReliabilityService:
    def __init__(
        self,
        reliability_repo: ReliabilityRepository,
        machine_repo: MachineRepository,
        maintenance_repo: MaintenanceRepository,
        risk_scorer: Optional[FailureRiskScorer] = None,
    ) -> None:
        self.rel_repo = reliability_repo
        self.mach_repo = machine_repo
        self.maint_repo = maintenance_repo
        self.scorer = risk_scorer or FailureRiskScorer()

    def evaluate_failure_risk(
        self,
        machine_id: str,
        features: FeatureVector,
        active_anomalies: List[Anomaly],
        failure_mode: FailureMode = FailureMode.BEARING_DEGRADATION,
    ) -> FailureRisk:
        """Calculate and persist failure risk for a machine."""
        failures = self.rel_repo.get_failure_history(machine_id)
        maint_events = self.maint_repo.get_maintenance_history(machine_id)

        risk = self.scorer.calculate_risk(
            machine_id=machine_id,
            features=features,
            active_anomalies=active_anomalies,
            historical_failures=failures,
            maintenance_history=maint_events,
            failure_mode=failure_mode,
        )

        # Persist FailureRisk
        self.rel_repo.save_failure_risk(risk)

        # Update HealthAssessment
        if risk.risk_score >= 0.80:
            status = HealthStatus.CRITICAL
            concern = f"Critical risk of {failure_mode.value} (Risk: {risk.risk_score:.2f})"
            health_score = round((1.0 - risk.risk_score) * 100.0, 1)
        elif risk.risk_score >= 0.50:
            status = HealthStatus.DEGRADING
            concern = f"Elevated degradation risk for {failure_mode.value} (Risk: {risk.risk_score:.2f})"
            health_score = round((1.0 - risk.risk_score) * 100.0, 1)
        else:
            status = HealthStatus.HEALTHY
            concern = None
            health_score = round((1.0 - risk.risk_score) * 100.0, 1)

        ha = HealthAssessment(
            assessment_id=f"HA-{machine_id}-{features.timestamp.strftime('%Y%m%d%H%M%S')}",
            machine_id=machine_id,
            health_status=status,
            health_score=health_score,
            primary_concern=concern,
            updated_at=features.timestamp,
        )
        self.rel_repo.save_health_assessment(ha)
        self.mach_repo.update_machine_health(machine_id, status)

        return risk

    def get_latest_risk(self, machine_id: str) -> Optional[FailureRisk]:
        return self.rel_repo.get_latest_failure_risk(machine_id)

    def get_latest_health_assessment(self, machine_id: str) -> Optional[HealthAssessment]:
        return self.rel_repo.get_latest_health_assessment(machine_id)
