"""Tests for failure predictors (BearingFailurePredictor & BaselineHeuristicPredictor)."""

from datetime import datetime, timezone
from domain.models import MLFailurePrediction
from ml.models.failure_predictor import BearingFailurePredictor, BaselineHeuristicPredictor


def test_bearing_failure_predictor_healthy_state():
    predictor = BearingFailurePredictor()
    healthy_features = {
        "vibration_rms": 1.1,
        "vibration_peak": 1.8,
        "vibration_kurtosis": 3.0,
        "vibration_crest_factor": 1.4,
        "vibration_trend_1h": 0.0,
        "vibration_trend_6h": 0.0,
        "vibration_std": 0.05,
        "temperature_c": 44.0,
        "temperature_rate_of_change": 0.0,
        "temperature_above_ambient": 19.0,
        "temperature_trend_1h": 0.0,
        "operating_hours": 1500.0,
        "cycles_since_maintenance": 8000.0,
        "vibration_temp_ratio": 0.025,
        "power_vibration_interaction": 0.9,
        "thermal_mechanical_stress_index": 0.3,
        "days_since_last_maintenance": 20.0,
        "cumulative_failures": 0.0,
        "previous_bearing_issues": 0.0,
        "recent_availability_pct": 98.0,
    }

    prob = predictor.predict_proba(healthy_features, horizon_hours=24)
    assert 0.0 <= prob <= 0.15, f"Healthy state probability should be low, got {prob}"

    pred = predictor.predict("M204", healthy_features, horizon_hours=24)
    assert isinstance(pred, MLFailurePrediction)
    assert pred.failure_probability == prob
    assert not pred.threshold_exceeded


def test_bearing_failure_predictor_degraded_state():
    predictor = BearingFailurePredictor()
    degraded_features = {
        "vibration_rms": 4.65,
        "vibration_peak": 7.8,
        "vibration_kurtosis": 5.4,
        "vibration_crest_factor": 2.1,
        "vibration_trend_1h": 0.65,
        "vibration_trend_6h": 0.45,
        "vibration_std": 0.55,
        "temperature_c": 78.5,
        "temperature_rate_of_change": 4.2,
        "temperature_above_ambient": 53.5,
        "temperature_trend_1h": 3.8,
        "operating_hours": 3200.0,
        "cycles_since_maintenance": 18000.0,
        "vibration_temp_ratio": 0.059,
        "power_vibration_interaction": 3.9,
        "thermal_mechanical_stress_index": 2.4,
        "days_since_last_maintenance": 95.0,
        "cumulative_failures": 2.0,
        "previous_bearing_issues": 1.0,
        "recent_availability_pct": 82.0,
    }

    prob = predictor.predict_proba(degraded_features, horizon_hours=24)
    assert prob >= 0.70, f"Degraded state probability should be high, got {prob}"

    pred = predictor.predict("M204", degraded_features, horizon_hours=24)
    assert pred.threshold_exceeded
    assert len(pred.top_contributing_features) > 0
    # Top features should include vibration or thermal stress
    keys = list(pred.top_contributing_features.keys())
    assert any("vibration" in k or "stress" in k or "temperature" in k for k in keys)


def test_baseline_heuristic_predictor():
    baseline = BaselineHeuristicPredictor()
    pred_healthy = baseline.predict("M204", {"vibration_rms": 1.2, "temperature_c": 42.0})
    assert pred_healthy.failure_probability < 0.20

    pred_degraded = baseline.predict("M204", {"vibration_rms": 4.5, "temperature_c": 75.0})
    assert pred_degraded.failure_probability > 0.80
