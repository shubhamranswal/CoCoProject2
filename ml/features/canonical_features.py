"""Canonical 29-Feature Pipeline for Milestone 3 Predictive Production Layer.

Implements the authoritative feature extraction logic from oee_v2:
- Warning-threshold normalization (1.0 = warning threshold)
- 7 Sensor Metrics: VIB, BTMP, CUR, WTMP, RPM, PRS, FLW
- 4 Statistics per sensor: mean, max, 7-day slope, 30-day relative baseline
- 1 Maintenance feature: days_since_maint with strict temporal cutoff (no future leakage)
- Total 29 canonical features
- Deterministic 7-day failure target labeling
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple
import numpy as np
import pandas as pd

SENSOR_TYPE_TO_CODE: Dict[str, str] = {
    "vibration_rms": "VIB",
    "vibration": "VIB",
    "bearing_temperature": "BTMP",
    "temperature": "BTMP",
    "motor_current": "CUR",
    "current": "CUR",
    "winding_temperature": "WTMP",
    "rotational_speed": "RPM",
    "rpm": "RPM",
    "hydraulic_pressure": "PRS",
    "pressure": "PRS",
    "coolant_flow": "FLW",
    "flow": "FLW",
}

SHORTHAND_KEYS = ["VIB", "BTMP", "CUR", "WTMP", "RPM", "PRS", "FLW"]

CANONICAL_FEATURE_NAMES: List[str] = []
for k in SHORTHAND_KEYS:
    CANONICAL_FEATURE_NAMES.extend([f"{k}_mean", f"{k}_max", f"{k}_slope7", f"{k}_rel30"])
CANONICAL_FEATURE_NAMES.append("days_since_maint")

QUALIFYING_FAILURE_CODES: Set[str] = {
    "BD-BRG",  # Bearing degradation / mechanical wear
    "BD-MTR",  # Motor winding / insulation degradation
    "BD-HYD",  # Hydraulic pressure loss / seal failure
    "BD-CLT",  # Coolant flow blockage / thermal runaway
    "BD-DRV",  # Drive misalignment / mechanical binding
}

FAILURE_HORIZON_DAYS: int = 7
MAX_DAYS_SINCE_MAINT: float = 120.0


def normalize_sensor_value(value: float, warn_threshold: float, threshold_direction: str = "above") -> float:
    """Normalize reading against warning threshold. 1.0 represents exactly at warning limit."""
    if warn_threshold <= 0:
        return 0.0
    if threshold_direction == "below":
        return round(warn_threshold / max(1e-6, value), 6)
    return round(value / warn_threshold, 6)


def compute_7d_slope(values: np.ndarray) -> float:
    """Compute 7-day linear slope (first degree polynomial fit). Requires at least 3 valid points."""
    valid_mask = ~np.isnan(values)
    if valid_mask.sum() < 3:
        return 0.0
    x = np.arange(len(values))[valid_mask]
    y = values[valid_mask]
    slope = float(np.polyfit(x, y, 1)[0])
    return round(slope, 6)


def compute_30d_relative(current_mean: float, baseline_window: np.ndarray) -> float:
    """Compute ratio of current daily mean to 30-day baseline median (days i-30 to i-7)."""
    valid_base = baseline_window[~np.isnan(baseline_window)]
    if len(valid_base) == 0:
        return 1.0
    med = float(np.nanmedian(valid_base))
    if med <= 1e-6 or np.isnan(med):
        return 1.0
    return round(current_mean / med, 4)


def build_canonical_feature_matrix(
    sensors_df: pd.DataFrame,
    hourly_readings_df: pd.DataFrame,
    work_orders_df: pd.DataFrame,
    target_horizon_days: int = 7,
) -> pd.DataFrame:
    """Build canonical 29-feature DataFrame with strictly leakage-free features and target labels."""
    h = hourly_readings_df.copy()
    if not np.issubdtype(h["ts"].dtype, np.datetime64):
        h["ts"] = pd.to_datetime(h["ts"])
    h["date"] = h["ts"].dt.normalize()

    sens = sensors_df[["sensor_id", "machine_id", "sensor_type", "warn_threshold", "threshold_direction"]].copy()
    sens["k"] = sens["sensor_type"].map(SENSOR_TYPE_TO_CODE)
    h = h.merge(sens, on="sensor_id")

    # Normalized reading
    x = h["avg_running"]
    h["norm"] = np.where(
        h["threshold_direction"] == "above",
        x / h["warn_threshold"],
        h["warn_threshold"] / x.where(x > 0, 1e-6),
    )

    daily = h.groupby(["machine_id", "k", "date"])["norm"].agg(["mean", "max"]).reset_index()
    all_dates = pd.date_range(h["date"].min(), h["date"].max())
    feats_dict: Dict[Tuple[str, str], pd.DataFrame] = {}

    for (m, k), g in daily.groupby(["machine_id", "k"]):
        g_reindexed = g.set_index("date").reindex(all_dates)
        mean_vals = g_reindexed["mean"].values
        max_vals = g_reindexed["max"].values
        n_dates = len(all_dates)
        slope_vals = np.zeros(n_dates, dtype=float)
        rel_vals = np.ones(n_dates, dtype=float)

        for i in range(n_dates):
            window_7d = mean_vals[max(0, i - 6) : i + 1]
            slope_vals[i] = compute_7d_slope(window_7d)

            if i >= 30:
                base_win = mean_vals[i - 30 : i - 7]
                rel_vals[i] = compute_30d_relative(mean_vals[i] if not np.isnan(mean_vals[i]) else 1.0, base_win)

        feats_dict[(m, k)] = pd.DataFrame(
            {
                "machine_id": m,
                "date": all_dates,
                f"{k}_mean": np.nan_to_num(mean_vals, nan=0.0),
                f"{k}_max": np.nan_to_num(max_vals, nan=0.0),
                f"{k}_slope7": slope_vals,
                f"{k}_rel30": rel_vals,
            }
        )

    # Merge all 7 sensor metric blocks
    X = None
    for k in SHORTHAND_KEYS:
        k_dfs = [df for (m, kk), df in feats_dict.items() if kk == k]
        if k_dfs:
            merged_k = pd.concat(k_dfs, ignore_index=True)
            X = merged_k if X is None else X.merge(merged_k, on=["machine_id", "date"], how="outer")

    # If some machines don't have all sensor types, fill missing columns with nominal values
    for col in CANONICAL_FEATURE_NAMES:
        if col not in X.columns and col != "days_since_maint":
            if col.endswith("_mean") or col.endswith("_max") or col.endswith("_slope7"):
                X[col] = 0.0
            elif col.endswith("_rel30"):
                X[col] = 1.0

    # Maintenance recency feature (strictly closed on or before feature_date)
    wo = work_orders_df.copy()
    if not np.issubdtype(wo["closed_ts"].dtype, np.datetime64):
        wo["closed_ts"] = pd.to_datetime(wo["closed_ts"])
    closed_wo = wo[wo["status"] == "closed"].sort_values("closed_ts")

    def calc_days_since_maint(row: pd.Series) -> float:
        # Strict temporal boundary: closed_ts <= row.date + 1 day (end of feature date)
        cutoff = row["date"] + pd.Timedelta(days=1)
        sub = closed_wo[(closed_wo["machine_id"] == row["machine_id"]) & (closed_wo["closed_ts"] <= cutoff)]
        if len(sub) > 0:
            last_closed = sub["closed_ts"].iloc[-1]
            diff_days = (cutoff - last_closed).total_seconds() / 86400.0
            return float(min(diff_days, MAX_DAYS_SINCE_MAINT))
        return MAX_DAYS_SINCE_MAINT

    X["days_since_maint"] = X.apply(calc_days_since_maint, axis=1)

    # 7-day future failure target labeling (started in (row.date, row.date + 7 days])
    if not np.issubdtype(wo["started_ts"].dtype, np.datetime64):
        wo["started_ts"] = pd.to_datetime(wo["started_ts"])
    failures = wo[(wo["wo_type"] == "corrective") & (wo["failure_code"].isin(QUALIFYING_FAILURE_CODES))].copy()
    failures["failure_date"] = failures["started_ts"].dt.normalize()

    def calc_label(row: pd.Series) -> int:
        f_dates = failures[failures["machine_id"] == row["machine_id"]]["failure_date"]
        # Future failure strictly strictly in (row.date, row.date + horizon]
        has_fail = ((f_dates > row["date"]) & (f_dates <= row["date"] + pd.Timedelta(days=target_horizon_days))).any()
        return 1 if has_fail else 0

    X["label"] = X.apply(calc_label, axis=1)
    return X.sort_values(["date", "machine_id"]).reset_index(drop=True)
