"""Deterministic industrial feature extraction for equipment telemetry.

Follows AGENT.md & architecture/architecture.md:
- Statistical: rolling RMS, peak, mean, stddev
- Temporal: linear rate of change (g/hr, °C/hr)
- Comparative: percentage baseline deviation
- Cross-signal: vibration-temperature Pearson correlation
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from domain.models import Baseline, FeatureVector, TelemetryMeasurement


def _calculate_slope_per_hour(times_and_values: List[Tuple[datetime, float]]) -> float:
    """Calculate linear trend (rate of change per hour) using least-squares regression."""
    if len(times_and_values) < 2:
        return 0.0

    t0 = times_and_values[0][0].timestamp()
    # Normalize time to hours from t0
    xs = [(t.timestamp() - t0) / 3600.0 for t, _ in times_and_values]
    ys = [val for _, val in times_and_values]

    n = len(xs)
    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_xy = sum(x * y for x, y in zip(xs, ys))
    sum_xx = sum(x * x for x in xs)

    denom = (n * sum_xx - sum_x * sum_x)
    if abs(denom) < 1e-9:
        return 0.0
    slope = (n * sum_xy - sum_x * sum_y) / denom
    return round(slope, 4)


def _calculate_pearson_correlation(xs: List[float], ys: List[float]) -> float:
    """Calculate Pearson correlation coefficient between two equal-length signals."""
    if len(xs) < 2 or len(xs) != len(ys):
        return 0.0

    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)

    denom = math.sqrt(var_x * var_y)
    if denom < 1e-9:
        return 0.0
    return round(cov / denom, 4)


class FeatureExtractor:
    """Extracts explainable engineering features from telemetry measurements."""

    def __init__(self, window_minutes: int = 15) -> None:
        self.window_minutes = window_minutes

    def extract_features(
        self,
        machine_id: str,
        measurements: List[TelemetryMeasurement],
        baselines: Optional[Dict[str, Baseline]] = None,
        timestamp: Optional[datetime] = None,
    ) -> FeatureVector:
        ts = timestamp or (measurements[-1].timestamp if measurements else datetime.now(timezone.utc))
        b_dict = baselines or {}

        # Separate measurements by sensor
        vib_pts = [(m.timestamp, m.value) for m in measurements if "VIB" in m.sensor_id]
        tmp_pts = [(m.timestamp, m.value) for m in measurements if "TMP" in m.sensor_id]
        rpm_pts = [(m.timestamp, m.value) for m in measurements if "RPM" in m.sensor_id]
        cur_pts = [(m.timestamp, m.value) for m in measurements if "CUR" in m.sensor_id]

        # 1. Vibration features
        if vib_pts:
            vib_vals = [val for _, val in vib_pts]
            n_vib = len(vib_vals)
            # Quadratic mean (RMS)
            vib_rms = round(math.sqrt(sum(v * v for v in vib_vals) / n_vib), 4)
            vib_peak = round(max(vib_vals) * 1.414, 4)
            mean_v = sum(vib_vals) / n_vib
            vib_std = round(math.sqrt(sum((v - mean_v) ** 2 for v in vib_vals) / n_vib), 4)
            vib_slope = _calculate_slope_per_hour(vib_pts)
        else:
            vib_rms, vib_peak, vib_std, vib_slope = 0.45, 0.63, 0.02, 0.0

        vib_base = b_dict.get("vibration_rms")
        if vib_base and vib_base.baseline_mean > 0:
            vib_dev_pct = round(((vib_rms - vib_base.baseline_mean) / vib_base.baseline_mean) * 100.0, 2)
        else:
            vib_dev_pct = 0.0

        # 2. Temperature features
        if tmp_pts:
            tmp_vals = [val for _, val in tmp_pts]
            n_tmp = len(tmp_vals)
            tmp_mean = round(sum(tmp_vals) / n_tmp, 2)
            tmp_slope = _calculate_slope_per_hour(tmp_pts)
        else:
            tmp_mean, tmp_slope = 58.5, 0.0

        tmp_base = b_dict.get("temperature")
        if tmp_base and tmp_base.baseline_mean > 0:
            tmp_dev_pct = round(((tmp_mean - tmp_base.baseline_mean) / tmp_base.baseline_mean) * 100.0, 2)
        else:
            tmp_dev_pct = 0.0

        # 3. RPM features
        if rpm_pts:
            rpm_vals = [val for _, val in rpm_pts]
            n_rpm = len(rpm_vals)
            rpm_mean = round(sum(rpm_vals) / n_rpm, 1)
            mean_r = rpm_mean
            rpm_var = round(sum((r - mean_r) ** 2 for r in rpm_vals) / n_rpm, 2)
        else:
            rpm_mean, rpm_var = 1750.0, 15.0

        rpm_base = b_dict.get("rpm")
        if rpm_base and rpm_base.baseline_mean > 0:
            rpm_dev_pct = round(((rpm_mean - rpm_base.baseline_mean) / rpm_base.baseline_mean) * 100.0, 2)
        else:
            rpm_dev_pct = 0.0

        # 4. Current features
        if cur_pts:
            cur_vals = [val for _, val in cur_pts]
            cur_mean = round(sum(cur_vals) / len(cur_vals), 2)
        else:
            cur_mean = 18.5

        # 5. Cross-signal correlation (Vibration vs Temperature)
        min_len = min(len(vib_pts), len(tmp_pts))
        if min_len >= 3:
            corr = _calculate_pearson_correlation(
                [v for _, v in vib_pts[:min_len]],
                [t for _, t in tmp_pts[:min_len]],
            )
        else:
            corr = 0.0

        feature_id = f"FEAT-{machine_id}-{ts.strftime('%Y%m%d%H%M%S')}"

        return FeatureVector(
            feature_id=feature_id,
            machine_id=machine_id,
            timestamp=ts,
            window_minutes=self.window_minutes,
            vibration_rms=vib_rms,
            vibration_peak=vib_peak,
            vibration_std=vib_std,
            vibration_rate_of_change=vib_slope,
            vibration_baseline_deviation_pct=vib_dev_pct,
            temperature_mean=tmp_mean,
            temperature_slope=tmp_slope,
            temperature_baseline_deviation_pct=tmp_dev_pct,
            rpm_mean=rpm_mean,
            rpm_variance=rpm_var,
            rpm_deviation_pct=rpm_dev_pct,
            current_mean=cur_mean,
            vibration_temperature_correlation=corr,
        )
