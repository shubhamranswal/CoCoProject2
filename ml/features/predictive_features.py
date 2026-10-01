"""24-feature pipeline for equipment failure prediction with temporal leakage prevention.

Follows Section 19:
- 7 Vibration features (RMS, peak, kurtosis, crest factor, trend 1h, trend 6h, std)
- 5 Temperature features (current, rate of change, above ambient, trend 1h, std)
- 4 Operating context features (hours, cycles, load pct, speed rpm)
- 3 Cross-signal features (vib/temp ratio, power-vib interaction, stress index)
- 3 Maintenance context features (days since maint, cumulative failures, previous bearing issues)
- 2 OEE features (availability pct, performance pct)

Strict temporal rule:
- feature_timestamp <= prediction_timestamp
- All measurements with timestamp > as_of are strictly excluded.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from domain.models import Baseline, MaintenanceEvent, TelemetryMeasurement
from ml.features.feature_extractor import _calculate_slope_per_hour

FEATURE_NAMES: List[str] = [
    "vibration_rms",
    "vibration_peak",
    "vibration_kurtosis",
    "vibration_crest_factor",
    "vibration_trend_1h",
    "vibration_trend_6h",
    "vibration_std",
    "temperature_c",
    "temperature_rate_of_change",
    "temperature_above_ambient",
    "temperature_trend_1h",
    "temperature_std",
    "operating_hours",
    "cycles_since_maintenance",
    "load_pct",
    "speed_rpm",
    "vibration_temp_ratio",
    "power_vibration_interaction",
    "thermal_mechanical_stress_index",
    "days_since_last_maintenance",
    "cumulative_failures",
    "previous_bearing_issues",
    "recent_availability_pct",
    "recent_performance_pct",
]


def _calc_kurtosis(values: List[float], mean: float, std: float) -> float:
    """Calculate sample kurtosis (excess kurtosis + 3, or standardized 4th moment)."""
    if len(values) < 4 or std < 1e-6:
        return 3.0  # Normal distribution kurtosis
    n = len(values)
    m4 = sum((x - mean) ** 4 for x in values) / n
    return round(m4 / (std ** 4), 4)


def extract_predictive_features(
    measurements: List[TelemetryMeasurement],
    as_of: datetime,
    baselines: Optional[Dict[str, Baseline]] = None,
    maintenance_events: Optional[List[MaintenanceEvent]] = None,
    operating_context: Optional[Dict[str, float]] = None,
    oee_context: Optional[Dict[str, float]] = None,
    ambient_temp_c: float = 22.0,
) -> Dict[str, float]:
    """Extract strictly leakage-free 24-feature vector as of a specific cutoff timestamp."""
    # Ensure timezone awareness
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)

    # 1. Temporal Leakage Prevention Filter
    valid_measurements = [
        m for m in measurements
        if (m.timestamp.replace(tzinfo=timezone.utc) if m.timestamp.tzinfo is None else m.timestamp) <= as_of
    ]

    vib_points: List[Tuple[datetime, float]] = []
    temp_points: List[Tuple[datetime, float]] = []

    for m in valid_measurements:
        sid = m.sensor_id.upper()
        unit = (m.unit or "").lower()
        if "VIB" in sid or unit in ("mm/s", "g", "m/s2"):
            vib_points.append((m.timestamp, float(m.value)))
        elif "TMP" in sid or "TEMP" in sid or "c" in unit:
            temp_points.append((m.timestamp, float(m.value)))

    # Sort chronologically
    vib_points.sort(key=lambda x: x[0])
    temp_points.sort(key=lambda x: x[0])

    # 1. Vibration Features
    vib_vals = [v for _, v in vib_points]
    if vib_vals:
        n_v = len(vib_vals)
        mean_v = sum(vib_vals) / n_v
        std_v = math.sqrt(sum((x - mean_v) ** 2 for x in vib_vals) / n_v) if n_v > 1 else 0.0
        rms_v = math.sqrt(sum(x ** 2 for x in vib_vals) / n_v)
        peak_v = max(abs(x) for x in vib_vals)
        crest_factor_v = (peak_v / rms_v) if rms_v > 1e-6 else 1.0
        kurtosis_v = _calc_kurtosis(vib_vals, mean_v, std_v)
    else:
        mean_v = 0.0
        std_v = 0.0
        rms_v = 0.0
        peak_v = 0.0
        crest_factor_v = 1.0
        kurtosis_v = 3.0

    # Trend 1h and 6h
    as_of_ts = as_of.timestamp()
    pts_1h = [(t, v) for t, v in vib_points if (as_of_ts - t.timestamp()) <= 3600]
    trend_1h = _calculate_slope_per_hour(pts_1h) if len(pts_1h) >= 2 else 0.0

    pts_6h = [(t, v) for t, v in vib_points if (as_of_ts - t.timestamp()) <= 21600]
    trend_6h = _calculate_slope_per_hour(pts_6h) if len(pts_6h) >= 2 else trend_1h

    # 2. Temperature Features
    temp_vals = [v for _, v in temp_points]
    if temp_vals:
        n_t = len(temp_vals)
        cur_temp = temp_vals[-1]
        mean_t = sum(temp_vals) / n_t
        std_t = math.sqrt(sum((x - mean_t) ** 2 for x in temp_vals) / n_t) if n_t > 1 else 0.0
    else:
        cur_temp = ambient_temp_c
        mean_t = ambient_temp_c
        std_t = 0.0

    pts_t_1h = [(t, v) for t, v in temp_points if (as_of_ts - t.timestamp()) <= 3600]
    temp_trend_1h = _calculate_slope_per_hour(pts_t_1h) if len(pts_t_1h) >= 2 else 0.0
    temp_rate_of_change = temp_trend_1h
    temp_above_ambient = max(0.0, cur_temp - ambient_temp_c)

    # 3. Operating Context Features
    op_ctx = operating_context or {}
    operating_hours = float(op_ctx.get("operating_hours", 2400.0))
    cycles = float(op_ctx.get("cycles_since_maintenance", 12500.0))
    load_pct = float(op_ctx.get("load_pct", 85.0))
    speed_rpm = float(op_ctx.get("speed_rpm", 1750.0))

    # 4. Cross-Signal Features
    vib_temp_ratio = round(rms_v / max(1.0, cur_temp), 4)
    power_interaction = round((load_pct / 100.0) * rms_v, 4)
    # Normalized thermal-mechanical stress
    stress_index = round((rms_v / 2.5) * (cur_temp / 60.0), 4)

    # 5. Maintenance Context Features
    maint_events = maintenance_events or []
    def _event_ts(ev: Any) -> datetime:
        raw_ts = getattr(ev, "timestamp", getattr(ev, "performed_at", None))
        if raw_ts is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        return raw_ts.replace(tzinfo=timezone.utc) if raw_ts.tzinfo is None else raw_ts

    # Only events strictly prior to as_of
    past_maint = [
        e for e in maint_events
        if _event_ts(e) <= as_of
    ]
    if past_maint:
        last_m = max(past_maint, key=_event_ts)
        days_since_maint = max(0.0, (as_of - _event_ts(last_m)).total_seconds() / 86400.0)
    else:
        days_since_maint = float(op_ctx.get("days_since_last_maintenance", 45.0))

    cum_failures = float(sum(1 for e in past_maint if "failure" in e.event_type.lower()))
    bearing_issues = float(sum(1 for e in past_maint if "bearing" in str(e.description or "").lower()))

    # 6. OEE Context Features
    oee = oee_context or {}
    availability_pct = float(oee.get("availability_pct", 92.5))
    performance_pct = float(oee.get("performance_pct", 88.0))

    features: Dict[str, float] = {
        "vibration_rms": round(rms_v, 4),
        "vibration_peak": round(peak_v, 4),
        "vibration_kurtosis": round(kurtosis_v, 4),
        "vibration_crest_factor": round(crest_factor_v, 4),
        "vibration_trend_1h": round(trend_1h, 4),
        "vibration_trend_6h": round(trend_6h, 4),
        "vibration_std": round(std_v, 4),
        "temperature_c": round(cur_temp, 4),
        "temperature_rate_of_change": round(temp_rate_of_change, 4),
        "temperature_above_ambient": round(temp_above_ambient, 4),
        "temperature_trend_1h": round(temp_trend_1h, 4),
        "temperature_std": round(std_t, 4),
        "operating_hours": round(operating_hours, 2),
        "cycles_since_maintenance": round(cycles, 1),
        "load_pct": round(load_pct, 2),
        "speed_rpm": round(speed_rpm, 1),
        "vibration_temp_ratio": vib_temp_ratio,
        "power_vibration_interaction": power_interaction,
        "thermal_mechanical_stress_index": stress_index,
        "days_since_last_maintenance": round(days_since_maint, 2),
        "cumulative_failures": cum_failures,
        "previous_bearing_issues": bearing_issues,
        "recent_availability_pct": round(availability_pct, 2),
        "recent_performance_pct": round(performance_pct, 2),
    }

    assert len(features) == 24, f"Expected 24 features, got {len(features)}"
    return features
