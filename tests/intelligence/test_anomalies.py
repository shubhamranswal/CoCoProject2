"""Tests verifying deterministic anomaly detection service."""

from datetime import datetime, timezone
import pytest

from domain.enums import Severity
from domain.models import Baseline, FeatureVector
from repositories.memory.memory_repository import InMemoryRepository
from services.anomaly_service import AnomalyService


@pytest.fixture
def repo_and_service():
    repo = InMemoryRepository()
    service = AnomalyService(repository=repo)
    return repo, service


@pytest.fixture
def baselines():
    return {
        "vibration_rms": Baseline(
            baseline_id="BASE-VIB",
            machine_id="M204",
            signal_name="vibration_rms",
            baseline_mean=0.45,
            baseline_std=0.03,
            warning_threshold=0.75,
            critical_threshold=1.00,
            unit="g",
        ),
        "temperature": Baseline(
            baseline_id="BASE-TMP",
            machine_id="M204",
            signal_name="temperature",
            baseline_mean=58.5,
            baseline_std=1.2,
            warning_threshold=75.0,
            critical_threshold=90.0,
            unit="°C",
        ),
    }


def test_nominal_features_generate_no_anomalies(repo_and_service, baselines):
    repo, service = repo_and_service
    fv = FeatureVector(
        feature_id="FV-1",
        machine_id="M204",
        timestamp=datetime.now(timezone.utc),
        vibration_rms=0.45,
        vibration_peak=0.64,
        temperature_mean=58.5,
        temperature_slope=0.1,
        rpm_mean=1750.0,
        rpm_variance=2.0,
        current_mean=18.5,
    )

    anomalies = service.detect_anomalies(fv, baselines)
    assert len(anomalies) == 0


def test_vibration_exceeding_warning_threshold_triggers_anomaly(repo_and_service, baselines):
    repo, service = repo_and_service
    fv = FeatureVector(
        feature_id="FV-2",
        machine_id="M204",
        timestamp=datetime.now(timezone.utc),
        vibration_rms=0.82,  # > warning (0.75), < critical (1.00)
        vibration_peak=1.20,
        temperature_mean=60.0,
        temperature_slope=0.1,
        rpm_mean=1750.0,
        rpm_variance=2.0,
        current_mean=18.5,
    )

    anomalies = service.detect_anomalies(fv, baselines)
    assert len(anomalies) >= 1
    vib_anom = next(a for a in anomalies if a.sensor_id == "SEN-M204-VIB")
    assert vib_anom.severity == Severity.MEDIUM
    assert vib_anom.score > 2.5


def test_coupled_vibration_and_temperature_triggers_multi_signal_anomaly(repo_and_service, baselines):
    repo, service = repo_and_service
    fv = FeatureVector(
        feature_id="FV-3",
        machine_id="M204",
        timestamp=datetime.now(timezone.utc),
        vibration_rms=0.85,
        vibration_peak=1.35,
        temperature_mean=78.0,  # elevated
        temperature_slope=3.5,  # high slope
        rpm_mean=1740.0,
        rpm_variance=5.0,
        current_mean=21.0,
        vibration_temperature_correlation=0.92,
    )

    anomalies = service.detect_anomalies(fv, baselines)
    # Should detect vibration anomaly, temperature anomaly, and coupled thermal-vibrational anomaly
    sensor_ids = [a.sensor_id for a in anomalies]
    assert "SEN-M204-VIB" in sensor_ids
    assert "SEN-M204-TMP" in sensor_ids
    metric_names = [a.metric_name for a in anomalies]
    assert "bearing_thermal_vibrational_coupling" in metric_names

