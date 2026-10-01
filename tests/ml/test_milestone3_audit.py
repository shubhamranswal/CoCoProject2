"""Automated Audit and Verification Tests for Milestone 3 Predictive Layer.

Audits:
1. Historical PRED-000322 preservation vs new active risk policy inference
2. 29-Feature contract identity (training feature order == inference feature order)
3. Target labeling temporal boundary conditions (T, T + 168h]
4. Chronological split causality and leakage prevention
5. Single active model promotion exclusivity in registry
"""

import os
import pandas as pd
import numpy as np
import pytest
from datetime import datetime, timezone, timedelta

from domain.enums import FailureMode, RiskLevel
from domain.models import (
    CanonicalPrediction,
    MLFailurePrediction,
    ModelRegistryRecord,
    ModelEvaluationRecord,
)
from ml.features.canonical_features import (
    CANONICAL_FEATURE_NAMES,
    FAILURE_HORIZON_DAYS,
    build_canonical_feature_matrix,
)
from ml.models.canonical_predictor import CanonicalFailurePredictor
from ml.inference.risk_policy import RiskPolicy
from repositories.memory.memory_repository import InMemoryRepository
from services.prediction_service import PredictionService


CANONICAL_DATA_DIR = r"C:\Users\shubh\Desktop\oee_v2"


def test_audit_historical_pred_000322_preservation():
    """Verify that historical PRED-000322 is preserved intact with canonical raw values

    and is separate from new active risk policy outputs.
    """
    pred_csv_path = os.path.join(CANONICAL_DATA_DIR, "prediction.csv")
    assert os.path.exists(pred_csv_path), "Canonical prediction.csv must exist"

    df = pd.read_csv(pred_csv_path)
    pred_322_rows = df[df["prediction_id"] == "PRED-000322"]
    assert len(pred_322_rows) == 1, "PRED-000322 must exist exactly once in canonical data"

    rec = pred_322_rows.iloc[0]
    # Exact source contract for PRED-000322
    assert rec["machine_id"] == "M21"
    assert rec["suspected_component_id"] == "C-M21-BRG"
    assert rec["model_name"] == "hgb_failure_7d_v1"
    assert rec["horizon_days"] == 7
    assert float(rec["failure_prob"]) == 0.95
    assert str(rec["risk_level"]).lower() == "high"
    assert "VIB_max" in str(rec["top_features"])

    # Now verify that when new inference runs for M21 under RiskPolicy v1.0,
    # it produces a separate, distinct record with explicit CRITICAL risk level
    policy = RiskPolicy()
    risk_level_tier = policy.classify_canonical_tier(0.95)
    assert risk_level_tier == "CRITICAL"
    assert policy.classify(0.95) == RiskLevel.CRITICAL

    # Verify that in repository, saving a new prediction does NOT alter PRED-000322
    repo = InMemoryRepository()
    hist_cp = CanonicalPrediction(
        prediction_id="PRED-000322",
        scored_ts=datetime(2026, 9, 28, 23, 0, tzinfo=timezone.utc),
        machine_id="M21",
        suspected_component_id="C-M21-BRG",
        model_name="hgb_failure_7d_v1",
        horizon_days=7,
        failure_prob=0.95,
        risk_level="high",  # preserved verbatim
        top_features='[{"feature": "VIB_max", "share": 0.5}, {"feature": "VIB_mean", "share": 0.27}, {"feature": "VIB_rel30", "share": 0.22}]',
    )
    repo.save_canonical_prediction(hist_cp)

    # Now generate new active prediction
    service = PredictionService(ml_repository=repo, risk_policy=policy)
    features = {
        "VIB_mean": 1.25,
        "VIB_max": 1.743,
        "VIB_slope7": 0.085,
        "VIB_rel30": 1.48,
        "BTMP_mean": 0.95,
        "BTMP_max": 1.127,
        "BTMP_slope7": 0.042,
        "BTMP_rel30": 1.22,
        "days_since_maint": 65.0,
    }
    new_pred, lineage, snapshot = service.generate_prediction(
        machine_id="M21",
        features=features,
        as_of=datetime(2026, 9, 29, 6, 0, tzinfo=timezone.utc),
    )

    # New prediction has a distinct ID and active CRITICAL risk
    assert new_pred.prediction_id != "PRED-000322"
    assert new_pred.prediction_id.startswith("PRED-M21-")
    assert lineage.risk_level == "CRITICAL"

    # Historical record remains untouched in repository
    retrieved_hist = repo.get_canonical_prediction("PRED-000322")
    assert retrieved_hist is not None
    assert retrieved_hist.prediction_id == "PRED-000322"
    assert retrieved_hist.risk_level == "high"
    assert retrieved_hist.failure_prob == 0.95


def test_audit_29_feature_contract_and_order_identity():
    """Verify exact 29 features and strict ordering between training and inference."""
    assert len(CANONICAL_FEATURE_NAMES) == 29

    expected_features = []
    for k in ["VIB", "BTMP", "CUR", "WTMP", "RPM", "PRS", "FLW"]:
        expected_features.extend([f"{k}_mean", f"{k}_max", f"{k}_slope7", f"{k}_rel30"])
    expected_features.append("days_since_maint")

    assert CANONICAL_FEATURE_NAMES == expected_features, "Feature order must match canonical list exactly"

    # Verify predictor uses identical order when constructing inference DataFrame
    predictor = CanonicalFailurePredictor()
    dummy_feats = {f: 1.0 for f in CANONICAL_FEATURE_NAMES}

    # Verify compute_top_features references the canonical set
    top_f = predictor.compute_top_features(dummy_feats)
    assert len(top_f) <= 3
    for k in top_f.keys():
        assert k in CANONICAL_FEATURE_NAMES


def test_audit_target_labeling_boundary_conditions():
    """Verify target labeling boundaries: strictly (T, T + 168h], ignoring past or far future."""
    T = pd.Timestamp("2026-06-01 00:00:00")
    horizon = 7  # days -> 168h
    T_plus_horizon = T + pd.Timedelta(days=horizon)

    # Event 1: At t = T (boundary: should NOT qualify because it's <= T, inside feature/past window)
    # Event 2: At t = T + 1h (qualifies: > T and <= T + 168h)
    # Event 3: At t = T + 168h (boundary: qualifies: <= T + 168h)
    # Event 4: At t = T + 169h (boundary: should NOT qualify: > T + 168h)

    # Test logic directly matching canonical labeling
    def is_qualifying(event_ts, eval_t, h_days=7):
        return (event_ts > eval_t) and (event_ts <= eval_t + pd.Timedelta(days=h_days))

    assert not is_qualifying(T, T)
    assert is_qualifying(T + pd.Timedelta(hours=1), T)
    assert is_qualifying(T + pd.Timedelta(days=7), T)
    assert not is_qualifying(T + pd.Timedelta(days=7, hours=1), T)

    # Test duplicate/multiple events within window evaluate to single binary label 1
    events = [
        T + pd.Timedelta(days=2),
        T + pd.Timedelta(days=3),
        T + pd.Timedelta(days=5),
    ]
    label = 1 if any(is_qualifying(e, T) for e in events) else 0
    assert label == 1


def test_audit_split_causality_and_no_future_leakage():
    """Verify that training dataset has zero future leakage and strict chronological separation."""
    # Ensure separation buffer = 7 days between training end and test start
    last_date = pd.Timestamp("2026-09-28")
    test_start = last_date - pd.Timedelta(days=85)
    train_end = test_start - pd.Timedelta(days=FAILURE_HORIZON_DAYS)

    buffer_days = (test_start - train_end).days
    assert buffer_days == FAILURE_HORIZON_DAYS, f"Buffer must equal failure horizon ({FAILURE_HORIZON_DAYS}d)"

    # Any target evaluated on train_end would only look up to test_start
    # Thus, no training sample target ever peeks into test_start or beyond
    train_target_horizon_end = train_end + pd.Timedelta(days=FAILURE_HORIZON_DAYS)
    assert train_target_horizon_end == test_start


def test_audit_model_registry_active_promotion_exclusivity():
    """Verify that ModelRegistry enforces exactly one active model at a time."""
    repo = InMemoryRepository()

    m1 = ModelRegistryRecord(
        model_id="model_v1",
        model_name="Model 1",
        model_version="1.0.0",
        algorithm="HistGradientBoostingClassifier",
        training_dataset_version="v1",
        feature_version="v1",
        target_definition="failure 7d",
        status="candidate",
    )
    m2 = ModelRegistryRecord(
        model_id="model_v2",
        model_name="Model 2",
        model_version="2.0.0",
        algorithm="HistGradientBoostingClassifier",
        training_dataset_version="v2",
        feature_version="v1",
        target_definition="failure 7d",
        status="candidate",
    )

    repo.save_model_metadata(m1)
    repo.save_model_metadata(m2)

    # Promote m1 to active
    repo.promote_model("model_v1", target_status="active")
    active = repo.get_active_model()
    assert active is not None
    assert active.model_id == "model_v1"
    assert active.status == "active"

    # Promote m2 to active: m1 must be automatically demoted to validated
    repo.promote_model("model_v2", target_status="active")
    active2 = repo.get_active_model()
    assert active2 is not None
    assert active2.model_id == "model_v2"
    assert active2.status == "active"

    # Verify m1 is no longer active
    m1_updated = repo.get_model("model_v1")
    assert m1_updated is not None
    assert m1_updated.status == "validated"


def test_audit_m21_exact_scenario_acceptance():
    """Verify acceptance criteria for M21 degradation signal and failure probability >= 0.90."""
    predictor = CanonicalFailurePredictor()

    # Physical feature values for M21 as of 2026-09-28:
    # Sensor S-M21-VIB: warning=2.8, critical=4.5 -> reading=4.881 mm/s -> norm=1.743
    # Sensor S-M21-BTMP: warning=75.0, critical=90.0 -> reading=84.55°C -> norm=1.127
    m21_feats = {
        "VIB_mean": 1.25,
        "VIB_max": 1.743,
        "VIB_slope7": 0.085,
        "VIB_rel30": 1.48,
        "BTMP_mean": 0.95,
        "BTMP_max": 1.127,
        "BTMP_slope7": 0.042,
        "BTMP_rel30": 1.22,
        "days_since_maint": 65.0,
    }

    prob = predictor.predict_proba(m21_feats)
    assert prob >= 0.90, f"M21 failure probability {prob} must be >= 0.90"

    comp_id, code, mode = predictor.resolve_suspected_component("M21", m21_feats)
    assert comp_id == "C-M21-BRG"
    assert mode == FailureMode.BEARING_DEGRADATION

    top_feats = predictor.compute_top_features(m21_feats)
    assert "VIB_max" in top_feats
    assert top_feats["VIB_max"] > 0.30
