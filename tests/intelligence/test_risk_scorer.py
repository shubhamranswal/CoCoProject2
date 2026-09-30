"""Tests verifying explainable FailureRiskScorer calculation and breakdown."""

from datetime import datetime, timedelta, timezone
import pytest

from domain.enums import FailureMode, RiskLevel, Severity
from domain.models import Anomaly, Failure, FeatureVector, MaintenanceEvent
from ml.inference.risk_scorer import FailureRiskScorer, RiskScoringConfig


def test_nominal_risk_scoring():
    scorer = FailureRiskScorer()
    now = datetime.now(timezone.utc)
    fv = FeatureVector(
        feature_id="FV-NOM",
        machine_id="M204",
        timestamp=now,
        vibration_rms=0.45,
        vibration_peak=0.64,
        temperature_mean=58.5,
        temperature_slope=0.0,
        rpm_mean=1750.0,
        rpm_variance=2.0,
        current_mean=18.5,
    )

    risk = scorer.calculate_risk(
        machine_id="M204",
        features=fv,
        active_anomalies=[],
        historical_failures=[],
        maintenance_history=[
            MaintenanceEvent(
                maintenance_id="M1",
                machine_id="M204",
                component_id="CMP-1",
                maintenance_type="INSPECTION",
                performed_at=now - timedelta(days=5),
                technician_name="Rajesh Kumar",
                duration_hours=1.0,
            )
        ],
    )

    assert risk.risk_score <= 0.15
    assert risk.risk_level == RiskLevel.LOW
    assert "vibration_deviation" in risk.contributing_factors


def test_high_risk_additive_breakdown():
    scorer = FailureRiskScorer()
    now = datetime.now(timezone.utc)
    fv = FeatureVector(
        feature_id="FV-HIGH",
        machine_id="M204",
        timestamp=now,
        vibration_rms=0.90,  # ~0.45 above baseline
        vibration_peak=1.85,
        temperature_mean=82.0,  # ~23.5 above baseline
        temperature_slope=3.5,  # rapid climb
        rpm_mean=1730.0,
        rpm_variance=10.0,
        current_mean=22.0,
    )

    anomalies = [
        Anomaly(
            anomaly_id="A1",
            machine_id="M204",
            sensor_id="SEN-M204-VIB",
            detected_at=now,
            severity=Severity.HIGH,
            score=3.5,
            metric_name="vibration_rms",
            observed_value=0.90,
            baseline_value=0.45,
            deviation_pct=100.0,
        ),
        Anomaly(
            anomaly_id="A2",
            machine_id="M204",
            sensor_id="SEN-M204-TMP",
            detected_at=now,
            severity=Severity.HIGH,
            score=3.0,
            metric_name="temperature",
            observed_value=82.0,
            baseline_value=58.5,
            deviation_pct=40.2,
        ),
    ]

    hist_failures = [
        Failure(
            failure_id="F1",
            machine_id="M204",
            component_id="CMP-M204-BRG",
            failure_mode=FailureMode.BEARING_DEGRADATION,
            occurred_at=now - timedelta(days=120),
            root_cause="Bearing spalling",
            downtime_hours=4.0,
            maintenance_action_taken="Replaced bearing",
        )
    ]

    risk = scorer.calculate_risk(
        machine_id="M204",
        features=fv,
        active_anomalies=anomalies,
        historical_failures=hist_failures,
        maintenance_history=[],
        failure_mode=FailureMode.BEARING_DEGRADATION,
    )

    assert risk.risk_score >= 0.80
    assert risk.risk_level == RiskLevel.CRITICAL
    assert len(risk.contributing_signals) > 0
    # Sum of factors should roughly match risk_score
    sum_factors = sum(risk.contributing_factors.values())
    assert pytest.approx(risk.risk_score, rel=1e-1) == sum_factors
