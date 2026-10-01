"""Tests for temporal leakage prevention in ML feature engineering."""

from datetime import datetime, timezone, timedelta
from domain.models import TelemetryMeasurement
from ml.features.predictive_features import extract_predictive_features


def test_strict_temporal_boundary_exclusion():
    cutoff = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)

    # Historical measurement (before cutoff)
    m_past = TelemetryMeasurement(
        measurement_id="M-PAST",
        machine_id="M204",
        sensor_id="M204-VIB-01",
        metric_name="vibration_rms",
        value=1.5,
        unit="mm/s",
        timestamp=cutoff - timedelta(minutes=15),
    )

    # Future measurement (after cutoff - temporal leakage candidate)
    m_future = TelemetryMeasurement(
        measurement_id="M-FUTURE",
        machine_id="M204",
        sensor_id="M204-VIB-01",
        metric_name="vibration_rms",
        value=9.9,  # Catastrophic failure value in the future
        unit="mm/s",
        timestamp=cutoff + timedelta(minutes=15),
    )

    # Extract with cutoff: future measurement MUST be ignored
    features_without_future = extract_predictive_features([m_past], as_of=cutoff)
    features_with_future = extract_predictive_features([m_past, m_future], as_of=cutoff)

    assert features_without_future["vibration_rms"] == 1.5
    assert features_with_future["vibration_rms"] == 1.5
    assert features_with_future["vibration_peak"] == 1.5
    assert features_with_future == features_without_future
