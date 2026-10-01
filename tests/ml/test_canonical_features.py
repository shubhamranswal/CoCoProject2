"""Unit and regression tests for canonical 29-feature pipeline and target labeling."""

from datetime import date, datetime, timedelta, timezone
import numpy as np
import pandas as pd
import pytest

from ml.features.canonical_features import (
    CANONICAL_FEATURE_NAMES,
    QUALIFYING_FAILURE_CODES,
    build_canonical_feature_matrix,
    compute_30d_relative,
    compute_7d_slope,
    normalize_sensor_value,
)


def test_29_canonical_feature_names():
    assert len(CANONICAL_FEATURE_NAMES) == 29
    assert "days_since_maint" in CANONICAL_FEATURE_NAMES
    for k in ["VIB", "BTMP", "CUR", "WTMP", "RPM", "PRS", "FLW"]:
        assert f"{k}_mean" in CANONICAL_FEATURE_NAMES
        assert f"{k}_max" in CANONICAL_FEATURE_NAMES
        assert f"{k}_slope7" in CANONICAL_FEATURE_NAMES
        assert f"{k}_rel30" in CANONICAL_FEATURE_NAMES


def test_normalize_sensor_value():
    # Above threshold direction: 1.0 represents warning threshold
    assert normalize_sensor_value(2.8, warn_threshold=2.8, threshold_direction="above") == 1.0
    assert normalize_sensor_value(4.2, warn_threshold=2.8, threshold_direction="above") == 1.5
    assert normalize_sensor_value(1.4, warn_threshold=2.8, threshold_direction="above") == 0.5

    # Below threshold direction (e.g. pressure/flow drop)
    assert normalize_sensor_value(50.0, warn_threshold=50.0, threshold_direction="below") == 1.0
    assert normalize_sensor_value(25.0, warn_threshold=50.0, threshold_direction="below") == 2.0


def test_compute_7d_slope():
    # Linear increase: 1.0, 2.0, 3.0 -> slope = 1.0
    arr = np.array([1.0, 2.0, 3.0, 4.0])
    slope = compute_7d_slope(arr)
    assert pytest.approx(slope, abs=1e-4) == 1.0

    # Constant: slope = 0.0
    arr_const = np.array([2.5, 2.5, 2.5, 2.5])
    assert compute_7d_slope(arr_const) == 0.0

    # Insufficient points (<3 valid points)
    arr_insufficient = np.array([np.nan, 2.0, np.nan])
    assert compute_7d_slope(arr_insufficient) == 0.0


def test_compute_30d_relative():
    # Current mean 2.0, baseline median 1.0 -> rel30 = 2.0
    baseline = np.array([1.0, 1.0, 1.0, 1.0, 1.0])
    assert compute_30d_relative(2.0, baseline) == 2.0

    # Empty / nan baseline defaults to 1.0
    assert compute_30d_relative(2.0, np.array([np.nan])) == 1.0


def test_canonical_feature_matrix_and_target_labeling():
    # Synthetic 35-day sequence for machine M1
    base_date = pd.Timestamp("2026-08-01")
    dates = pd.date_range(base_date, periods=35, freq="D")

    sensors_df = pd.DataFrame([
        {
            "sensor_id": "S1",
            "machine_id": "M1",
            "sensor_type": "vibration_rms",
            "warn_threshold": 2.8,
            "threshold_direction": "above",
        },
        {
            "sensor_id": "S2",
            "machine_id": "M1",
            "sensor_type": "bearing_temperature",
            "warn_threshold": 75.0,
            "threshold_direction": "above",
        },
    ])

    readings = []
    for d in dates:
        readings.append({"sensor_id": "S1", "ts": d, "avg_running": 2.8, "max_running": 3.0})
        readings.append({"sensor_id": "S2", "ts": d, "avg_running": 75.0, "max_running": 80.0})
    hourly_df = pd.DataFrame(readings)

    # Maintenance work orders:
    # 1. Closed maintenance on 2026-08-10
    # 2. Corrective failure starting on 2026-08-25 (qualifying code BD-BRG)
    wo_df = pd.DataFrame([
        {
            "wo_id": "WO1",
            "machine_id": "M1",
            "status": "closed",
            "wo_type": "preventive",
            "failure_code": None,
            "started_ts": pd.Timestamp("2026-08-10 08:00:00"),
            "closed_ts": pd.Timestamp("2026-08-10 12:00:00"),
        },
        {
            "wo_id": "WO2",
            "machine_id": "M1",
            "status": "closed",
            "wo_type": "corrective",
            "failure_code": "BD-BRG",
            "started_ts": pd.Timestamp("2026-08-25 09:00:00"),
            "closed_ts": pd.Timestamp("2026-08-25 15:00:00"),
        },
    ])

    matrix = build_canonical_feature_matrix(sensors_df, hourly_df, wo_df, target_horizon_days=7)

    assert len(matrix) == 35
    for feat in CANONICAL_FEATURE_NAMES:
        assert feat in matrix.columns, f"Missing canonical feature: {feat}"
    assert "label" in matrix.columns

    # Label verification:
    # Failure is on 2026-08-25.
    # The 7-day window before the failure (dates in [2026-08-18, 2026-08-24]) MUST have label=1.
    # Dates on or after 2026-08-25 or before 2026-08-18 must have label=0.
    sub_pos = matrix[(matrix["date"] >= "2026-08-18") & (matrix["date"] <= "2026-08-24")]
    assert (sub_pos["label"] == 1).all(), "Dates within 7 days prior to failure must be labeled 1"

    sub_zero = matrix[(matrix["date"] < "2026-08-18") | (matrix["date"] > "2026-08-25")]
    assert (sub_zero["label"] == 0).all(), "Dates outside 7-day window must be labeled 0"
