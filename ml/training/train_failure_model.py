"""Train a 7-day-ahead failure classifier from the OEE canonical dataset and score the latest 14 days.

Authoritative reference training pipeline from oee_v2 canonical package.
Usage: python -m ml.training.train_failure_model [data_dir]
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score, average_precision_score

from config import get_settings


def train_and_score(data_dir: str = None) -> pd.DataFrame:
    if not data_dir:
        settings = get_settings()
        data_dir = getattr(settings, "canonical_source_root", r"C:\Users\shubh\Desktop\oee_v2")

    D = data_dir
    HORIZON = 7
    FAIL_CODES = {"BD-BRG", "BD-MTR", "BD-HYD", "BD-CLT", "BD-DRV"}  # degradation-type failures

    sens = pd.read_csv(os.path.join(D, "sensor.csv"))

    # Handle hourly sensor reading path (direct csv, gz, or nested dir)
    hourly_path = os.path.join(D, "sensor_reading_hourly.csv.gz")
    if not os.path.exists(hourly_path):
        hourly_path = os.path.join(D, "sensor_reading_hourly.csv")
    if os.path.isdir(hourly_path):
        hourly_path = os.path.join(hourly_path, "sensor_reading_hourly.csv")

    h = pd.read_csv(hourly_path, parse_dates=["ts"])
    wo = pd.read_csv(os.path.join(D, "maintenance_work_order.csv"), parse_dates=["started_ts", "closed_ts"])

    # 1. Features: normalise each sensor against its warning threshold (1.0 = at warning level)
    h = h.merge(sens[["sensor_id", "machine_id", "sensor_type", "warn_threshold", "threshold_direction"]], on="sensor_id")
    x = h.avg_running
    h["norm"] = np.where(h.threshold_direction == "above", x / h.warn_threshold, h.warn_threshold / x.where(x > 0))
    h["date"] = h.ts.dt.normalize()
    SH = {
        "vibration_rms": "VIB",
        "bearing_temperature": "BTMP",
        "motor_current": "CUR",
        "winding_temperature": "WTMP",
        "rotational_speed": "RPM",
        "hydraulic_pressure": "PRS",
        "coolant_flow": "FLW",
    }
    h["k"] = h.sensor_type.map(SH)
    daily = h.groupby(["machine_id", "k", "date"]).norm.agg(["mean", "max"]).reset_index()
    dates = pd.date_range(h.date.min(), h.date.max())
    feats = {}
    for (m, k), g in daily.groupby(["machine_id", "k"]):
        g = g.set_index("date").reindex(dates)
        mean = g["mean"].values
        mx = g["max"].values
        slope = np.full(len(dates), np.nan)
        rel = np.full(len(dates), np.nan)
        for i in range(len(dates)):
            w = mean[max(0, i - 6) : i + 1]
            ok = ~np.isnan(w)
            if ok.sum() >= 3:
                slope[i] = np.polyfit(np.arange(len(w))[ok], w[ok], 1)[0]
            if i >= 30:
                base = np.nanmedian(mean[i - 30 : i - 7]) if (~np.isnan(mean[i - 30 : i - 7])).any() else np.nan
                rel[i] = mean[i] / base if base and not np.isnan(base) else np.nan
        feats[(m, k)] = pd.DataFrame({"machine_id": m, "date": dates, f"{k}_mean": mean, f"{k}_max": mx, f"{k}_slope7": slope, f"{k}_rel30": rel})

    X = None
    for k in SH.values():
        parts = pd.concat([v for (m, kk), v in feats.items() if kk == k]) if any(kk == k for (_, kk) in feats) else None
        if parts is not None:
            X = parts if X is None else X.merge(parts, on=["machine_id", "date"], how="outer")

    closed = wo[wo.status == "closed"].sort_values("closed_ts")

    def days_since(row):
        c = closed[(closed.machine_id == row.machine_id) & (closed.closed_ts <= row.date + pd.Timedelta(days=1))]
        return min((row.date + pd.Timedelta(days=1) - c.closed_ts.iloc[-1]).days, 120) if len(c) else 120

    X["days_since_maint"] = X.apply(days_since, axis=1)
    X = X.dropna(subset=[c for c in X.columns if c.endswith("_mean")], how="all").reset_index(drop=True)

    # 2. Labels from maintenance records: degradation failure starts in the next 7 days
    fail = wo[(wo.wo_type == "corrective") & wo.failure_code.isin(FAIL_CODES)][["machine_id", "started_ts"]].copy()
    fail["d"] = fail.started_ts.dt.normalize()

    def label(row):
        f = fail[fail.machine_id == row.machine_id].d
        return int(((f > row.date) & (f <= row.date + pd.Timedelta(days=HORIZON))).any())

    X["label"] = X.apply(label, axis=1)
    FEATS = [c for c in X.columns if c not in ("machine_id", "date", "label")]

    # 3. Time-based split (never random: avoids leaking the future)
    last = X.date.max()
    test_start = last - pd.Timedelta(days=85)
    train_end = test_start - pd.Timedelta(days=HORIZON)
    tr = X[X.date < train_end]
    te = X[(X.date >= test_start) & (X.date <= last - pd.Timedelta(days=HORIZON))]
    model = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.06, max_depth=4, l2_regularization=1.0, random_state=0)
    model.fit(tr[FEATS], tr.label, sample_weight=np.where(tr.label == 1, 3.0, 1.0))
    p = model.predict_proba(te[FEATS])[:, 1]
    pred = p >= 0.5
    y = te.label.values

    print(f"train rows {len(tr)} (positives {tr.label.mean():.1%}) | test rows {len(te)} (positives {y.mean():.1%})")
    print(f"AUC {roc_auc_score(y, p):.3f} | PR-AUC {average_precision_score(y, p):.3f} | precision@0.5 {(y[pred]==1).mean():.2f} | recall@0.5 {(pred[y==1]).mean():.2f}")

    # 4. Explainability: global importance x how unusual each feature is today
    imp = permutation_importance(model, te[FEATS], te.label, n_repeats=3, scoring="roc_auc", random_state=0).importances_mean.clip(min=0)
    mu, sd = tr[FEATS].mean(), tr[FEATS].std().replace(0, 1)

    # 5. Score the last 14 days
    sc = X[X.date > last - pd.Timedelta(days=14)].copy()
    sc["p"] = model.predict_proba(sc[FEATS])[:, 1]
    stype_comp = sens.assign(k=sens.sensor_type.map(SH)).groupby(["machine_id", "k"]).component_id.first().to_dict()
    rows = []
    for r in sc.itertuples(index=False):
        z = ((pd.Series(r._asdict())[FEATS].astype(float) - mu) / sd).fillna(0).clip(lower=0) * imp
        top = z.sort_values(ascending=False).head(3)
        tot = top.sum() or 1
        mx = {k: getattr(r, f"{k}_max", np.nan) for k in SH.values()}
        mx = {k: v for k, v in mx.items() if v == v}
        comp = stype_comp.get((r.machine_id, max(mx, key=mx.get))) if mx else ""
        rows.append(
            dict(
                scored_ts=r.date + pd.Timedelta(hours=23),
                machine_id=r.machine_id,
                suspected_component_id=comp,
                model_name="hgb_failure_7d_v1",
                horizon_days=HORIZON,
                failure_prob=round(float(r.p), 3),
                risk_level="high" if r.p >= 0.7 else "medium" if r.p >= 0.4 else "low",
                top_features=json.dumps([{"feature": f, "share": round(float(v / tot), 2)} for f, v in top.items()]),
            )
        )
    out = pd.DataFrame(rows).sort_values(["scored_ts", "machine_id"]).reset_index(drop=True)
    out.insert(0, "prediction_id", [f"PRED-{i+1:06d}" for i in range(len(out))])
    return out


if __name__ == "__main__":
    target_dir = sys.argv[1] if len(sys.argv) > 1 else None
    preds = train_and_score(target_dir)
    print(f"Generated {len(preds)} predictions.")
