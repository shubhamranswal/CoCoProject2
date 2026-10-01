"""Tests for 24-feature predictive extraction pipeline."""

from datetime import datetime, timezone, timedelta
from domain.models import TelemetryMeasurement
from ml.features.predictive_features import extract_predictive_features, FEATURE_NAMES


def test_24_features_extracted():
    now = datetime.now(timezone.utc)
    measurements = [
        TelemetryMeasurement(
            measurement_id="M1",
            machine_id="M204",
            sensor_id="M204-VIB-01",
            metric_name="vibration_rms",
            value=1.5,
            unit="mm/s",
            timestamp=now - timedelta(minutes=10),
        ),
        TelemetryMeasurement(
            measurement_id="M2",
            machine_id="M204",
            sensor_id="M204-VIB-01",
            metric_name="vibration_rms",
            value=2.0,
            unit="mm/s",
            timestamp=now - timedelta(minutes=5),
        ),
        TelemetryMeasurement(
            measurement_id="M3",
            machine_id="M204",
            sensor_id="M204-TEMP-01",
            metric_name="temperature_c",
            value=48.0,
            unit="C",
            timestamp=now - timedelta(minutes=5),
        ),
    ]

    features = extract_predictive_features(measurements, as_of=now)
    assert len(features) == 24
    for name in FEATURE_NAMES:
        assert name in features, f"Missing feature: {name}"
        assert isinstance(features[name], (int, float))
