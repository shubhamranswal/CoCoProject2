"""Unit and integration tests for PredictionService, model registry, lineage, and idempotency."""

from datetime import datetime, timezone
import pytest

from domain.enums import FailureMode, RiskLevel
from domain.models import (
    ModelRegistryRecord,
    ModelEvaluationRecord,
    PredictionFeatureSnapshot,
    PredictionLineage,
    MLFailurePrediction,
)
from ml.models.canonical_predictor import CanonicalFailurePredictor
from ml.inference.risk_policy import RiskPolicy
from repositories.memory.memory_repository import InMemoryRepository
from services.prediction_service import PredictionService


def test_model_registry_lifecycle():
    repo = InMemoryRepository(seed=False)

    m1 = ModelRegistryRecord(
        model_id="hgb_v1",
        model_name="Canonical 7-Day Failure Predictor",
        model_version="1.0.0",
        algorithm="HistGradientBoostingClassifier",
        training_dataset_version="v2026.03-canonical",
        feature_version="v1.0-29feat",
        target_definition="qualifying failure in (T, T + 7d]",
        horizon_hours=168,
        status="candidate",
    )
    repo.save_model_metadata(m1)

    # Candidate is not active yet
    assert repo.get_active_model() is None
    assert repo.get_model("hgb_v1") is not None
    assert repo.get_model("hgb_v1").status == "candidate"

    # Promote to active
    repo.promote_model("hgb_v1", target_status="active")
    active = repo.get_active_model()
    assert active is not None
    assert active.model_id == "hgb_v1"
    assert active.status == "active"

    # Save evaluation
    ev = ModelEvaluationRecord(
        evaluation_id="EVAL-001",
        model_id="hgb_v1",
        model_version="1.0.0",
        split_name="test",
        sample_count=1000,
        positive_count=50,
        roc_auc=0.92,
        pr_auc=0.65,
        precision_score=0.78,
        recall_score=0.70,
        f1_score=0.74,
        confusion_matrix={"tp": 35, "fp": 10, "tn": 940, "fn": 15},
    )
    repo.save_evaluation(ev)
    evals = repo.list_evaluations("hgb_v1")
    assert len(evals) == 1
    assert evals[0].roc_auc == 0.92


def test_prediction_service_generates_snapshot_and_lineage():
    repo = InMemoryRepository(seed=False)
    service = PredictionService(ml_repository=repo)

    as_of = datetime(2026, 9, 28, 23, 0, 0, tzinfo=timezone.utc)
    features = {
        "VIB_mean": 1.25,
        "VIB_max": 1.74,
        "VIB_slope7": 0.12,
        "VIB_rel30": 1.45,
        "BTMP_mean": 0.85,
        "BTMP_max": 1.13,
        "days_since_maint": 65.0,
    }

    pred, lineage, snapshot = service.generate_prediction(
        machine_id="M21",
        features=features,
        as_of=as_of,
    )

    # Check Prediction
    assert pred.machine_id == "M21"
    assert pred.component_id == "C-M21-BRG"
    assert pred.failure_mode == FailureMode.BEARING_DEGRADATION
    assert pred.failure_probability > 0.70
    assert pred.prediction_horizon_hours == 168
    assert "VIB_max" in pred.top_contributing_features

    # Check Snapshot
    assert snapshot.snapshot_id == f"SNAP-M21-{int(as_of.timestamp())}"
    assert snapshot.features["VIB_max"] == 1.74
    saved_snap = repo.get_prediction_feature_snapshot(snapshot.snapshot_id)
    assert saved_snap is not None
    assert saved_snap.machine_id == "M21"

    # Check Lineage
    assert lineage.lineage_id == f"LIN-M21-{int(as_of.timestamp())}"
    assert lineage.prediction_id == pred.prediction_id
    assert lineage.snapshot_id == snapshot.snapshot_id
    assert lineage.failure_probability == pred.failure_probability
    assert lineage.risk_level == "CRITICAL"

    saved_lineage = repo.get_prediction_lineage(pred.prediction_id)
    assert saved_lineage is not None
    assert saved_lineage.lineage_id == lineage.lineage_id


def test_prediction_service_strict_idempotency():
    repo = InMemoryRepository(seed=False)
    service = PredictionService(ml_repository=repo)

    as_of = datetime(2026, 9, 28, 23, 0, 0, tzinfo=timezone.utc)
    features = {"VIB_mean": 0.5, "VIB_max": 0.8}

    # First call
    pred1, lin1, snap1 = service.generate_prediction(machine_id="M1", features=features, as_of=as_of)

    # Second call with identical key
    pred2, lin2, snap2 = service.generate_prediction(machine_id="M1", features=features, as_of=as_of)

    # Must be identical references/content
    assert pred1.prediction_id == pred2.prediction_id
    assert lin1.lineage_id == lin2.lineage_id
    assert snap1.snapshot_id == snap2.snapshot_id

    # Repository must contain exactly one prediction for this machine
    stored_preds = repo.get_predictions_for_machine("M1")
    assert len(stored_preds) == 1
