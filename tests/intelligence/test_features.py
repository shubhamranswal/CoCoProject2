"""Tests verifying industrial feature engineering calculation accuracy."""

from datetime import datetime, timedelta, timezone
import pytest

from domain.models import Baseline, TelemetryMeasurement
from ml.features.feature_extractor import FeatureExtractor


@pytest.fixture
def sample_baselines():
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


def test_feature_extractor_rms_and_peak(sample_baselines):
    extractor = FeatureExtractor(window_minutes=15)
    t0 = datetime(2026, 3, 30, 10, 0, 0, tzinfo=timezone.utc)

    # 3 measurements of vibration: 0.40, 0.50, 0.60
    # Mean square = (0.16 + 0.25 + 0.36) / 3 = 0.77 / 3 = 0.256667 -> sqrt = 0.5066
    measurements = [
        TelemetryMeasurement(
            measurement_id=f"M{i}",
            machine_id="M204",
            sensor_id="SEN-M204-VIB",
            timestamp=t0 + timedelta(minutes=i * 5),
            value=v,
            unit="g",
        )
        for i, v in enumerate([0.40, 0.50, 0.60])
    ]

    features = extractor.extract_features(
        machine_id="M204",
        measurements=measurements,
        baselines=sample_baselines,
        timestamp=t0 + timedelta(minutes=10),
    )

    assert pytest.approx(features.vibration_rms, rel=1e-2) == 0.5066
    assert features.vibration_peak == round(0.60 * 1.414, 4)
    assert features.vibration_baseline_deviation_pct > 0.0


def test_temperature_slope_calculation():
    extractor = FeatureExtractor(window_minutes=60)
    t0 = datetime(2026, 3, 30, 10, 0, 0, tzinfo=timezone.utc)

    # Temperature climbing from 60°C to 63°C over 30 minutes -> slope = 3°C / 0.5 hr = +6.0°C/hr
    measurements = [
        TelemetryMeasurement(
            measurement_id="T0",
            machine_id="M204",
            sensor_id="SEN-M204-TMP",
            timestamp=t0,
            value=60.0,
            unit="°C",
        ),
        TelemetryMeasurement(
            measurement_id="T1",
            machine_id="M204",
            sensor_id="SEN-M204-TMP",
            timestamp=t0 + timedelta(minutes=30),
            value=63.0,
            unit="°C",
        ),
    ]

    features = extractor.extract_features(
        machine_id="M204",
        measurements=measurements,
        baselines={},
        timestamp=t0 + timedelta(minutes=30),
    )

    assert pytest.approx(features.temperature_slope, rel=1e-2) == 6.0
    assert pytest.approx(features.temperature_mean, rel=1e-2) == 61.5


def test_vibration_temperature_correlation():
    extractor = FeatureExtractor(window_minutes=60)
    t0 = datetime(2026, 3, 30, 10, 0, 0, tzinfo=timezone.utc)

    # Perfectly co-varying vibration and temperature
    measurements = []
    for i in range(5):
        ts = t0 + timedelta(minutes=i * 5)
        measurements.append(
            TelemetryMeasurement(
                measurement_id=f"V{i}",
                machine_id="M204",
                sensor_id="SEN-M204-VIB",
                timestamp=ts,
                value=0.50 + i * 0.10,
                unit="g",
            )
        )
        measurements.append(
            TelemetryMeasurement(
                measurement_id=f"T{i}",
                machine_id="M204",
                sensor_id="SEN-M204-TMP",
                timestamp=ts,
                value=60.0 + i * 2.0,
                unit="°C",
            )
        )

    features = extractor.extract_features(
        machine_id="M204",
        measurements=measurements,
        baselines={},
        timestamp=t0 + timedelta(minutes=20),
    )

    # Correlation should be close to 1.0
    assert features.vibration_temperature_correlation > 0.95
