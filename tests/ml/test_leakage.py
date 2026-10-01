"""Tests for temporal leakage prevention in ML feature engineering."""

from datetime import datetime, timezone, timedelta
from domain.models import TelemetryMeasurement, MaintenanceEvent
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


def test_days_since_maint_leakage_prevention():
    """Verify that future maintenance events (e.g. 2026-09-30) do not leak into earlier feature dates (e.g. 2026-09-25)."""
    feature_as_of = datetime(2026, 9, 25, 12, 0, 0, tzinfo=timezone.utc)

    past_event = MaintenanceEvent(
        maintenance_id="MAINT-PAST",
        machine_id="M21",
        maintenance_type="REPLACEMENT",
        performed_at=datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc),
        technician_name="T01",
        duration_hours=2.5,
        notes="Replaced bearing",
    )

    future_event = MaintenanceEvent(
        maintenance_id="MAINT-FUTURE",
        machine_id="M21",
        maintenance_type="REPLACEMENT",
        performed_at=datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc),
        technician_name="T01",
        duration_hours=3.0,
        notes="Future scheduled maintenance",
    )

    # Feature extraction with only past maintenance
    feat_past_only = extract_predictive_features(
        measurements=[],
        as_of=feature_as_of,
        maintenance_events=[past_event],
    )

    # Feature extraction with past AND future maintenance included in the source records
    feat_with_future = extract_predictive_features(
        measurements=[],
        as_of=feature_as_of,
        maintenance_events=[past_event, future_event],
    )

    # Both must report exactly 5.0 days since last maintenance as of 2026-09-25
    assert feat_past_only["days_since_last_maintenance"] == 5.0
    assert feat_with_future["days_since_last_maintenance"] == 5.0
    assert feat_with_future["days_since_last_maintenance"] == feat_past_only["days_since_last_maintenance"]


def test_sql_feature_daily_maint_leakage_constraint():
    """Verify that V_MACHINE_FEATURE_DAILY SQL enforces strict temporal bounds on maintenance events."""
    from pathlib import Path
    ddl_path = Path("snowflake/ddl/coco_factory/40_ml_foundation.sql")
    assert ddl_path.exists(), "40_ml_foundation.sql not found"
    content = ddl_path.read_text(encoding="utf-8")

    assert "DATE(w.closed_ts) <= rf.feature_date" in content, (
        "V_MACHINE_FEATURE_DAILY must filter maintenance by DATE(w.closed_ts) <= rf.feature_date"
    )
    assert "MAX(DATE(w.closed_ts))" in content, (
        "V_MACHINE_FEATURE_DAILY must take the MAX closed_ts before the feature date"
    )
