"""Acceptance test verifying the canonical M21 predictive reliability scenario for Milestone 3.

Validates:
1. Canonical historical prediction PRED-000322 is preserved intact.
2. Newly generated production prediction identifies the M21 drive-end bearing failure pattern:
   - Machine: M21 (Grinder 3)
   - Component: C-M21-BRG (Drive-End Bearing)
   - Failure code: BD-BRG (Bearing Degradation)
   - High/Critical probability from severe vibration (4.881 mm/s) & temperature (84.55°C) exceedances
   - Top contributing features: VIB_max, VIB_mean, VIB_rel30
3. Complete auditable prediction lineage and feature snapshot persistence.
4. Idempotency on repeated execution.
"""

from datetime import datetime, timezone
import pytest

from domain.enums import FailureMode, RiskLevel
from ml.models.canonical_predictor import CanonicalFailurePredictor
from ml.inference.risk_policy import RiskPolicy
from repositories.memory.memory_repository import InMemoryRepository
from services.prediction_service import PredictionService


def test_m21_canonical_historical_prediction_preserved():
    """Verify that canonical historical prediction PRED-000322 remains preserved in repository."""
    repo = InMemoryRepository(seed=True)
    canonical_pred = repo.get_canonical_prediction("PRED-000322")

    assert canonical_pred is not None
    assert canonical_pred.machine_id == "M21"
    assert canonical_pred.suspected_component_id == "C-M21-BRG"
    assert canonical_pred.failure_prob == 0.95
    assert canonical_pred.risk_level in ("high", "CRITICAL")
    assert "VIB_max" in canonical_pred.top_features


def test_m21_production_inference_and_lineage():
    """Verify that newly generated prediction reproduces the M21 degradation signals with full provenance."""
    repo = InMemoryRepository(seed=True)
    policy = RiskPolicy()
    service = PredictionService(ml_repository=repo, risk_policy=policy)

    as_of = datetime(2026, 9, 28, 23, 0, 0, tzinfo=timezone.utc)

    # Physical feature values for M21 as of 2026-09-28:
    # Sensor S-M21-VIB: warning=2.8, critical=4.5 -> reading=4.881 mm/s -> norm=1.743
    # Sensor S-M21-BTMP: warning=75.0, critical=90.0 -> reading=84.55°C -> norm=1.127
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

    pred, lineage, snapshot = service.generate_prediction(
        machine_id="M21",
        features=features,
        as_of=as_of,
        component_id="C-M21-BRG",
    )

    # 1. Distinct new prediction record with dedicated ID
    assert pred.prediction_id != "PRED-000322"
    assert pred.prediction_id == f"PRED-M21-{int(as_of.timestamp())}"
    assert pred.machine_id == "M21"
    assert pred.component_id == "C-M21-BRG"
    assert pred.failure_mode == FailureMode.BEARING_DEGRADATION

    # 2. Probability and Risk Tier
    assert pred.failure_probability >= 0.85, f"Expected high failure probability, got {pred.failure_probability}"
    assert lineage.risk_level == "high"
    assert policy.classify_risk_level(pred.failure_probability) == RiskLevel.CRITICAL

    # 3. Top Contributing Features
    top_keys = list(pred.top_contributing_features.keys())
    assert "VIB_max" in top_keys
    assert "VIB_mean" in top_keys or "VIB_rel30" in top_keys

    # 4. Feature Snapshot Verification
    assert snapshot.snapshot_id == f"SNAP-M21-{int(as_of.timestamp())}"
    assert snapshot.features["VIB_max"] == 1.743
    assert snapshot.feature_version == "v1.0-29feat"

    # 5. Lineage Verification
    assert lineage.lineage_id == f"LIN-M21-{int(as_of.timestamp())}"
    assert lineage.prediction_id == pred.prediction_id
    assert lineage.snapshot_id == snapshot.snapshot_id
    assert lineage.policy_version == policy.version

    # 6. Idempotency Check
    pred_repeat, lineage_repeat, snapshot_repeat = service.generate_prediction(
        machine_id="M21",
        features=features,
        as_of=as_of,
        component_id="C-M21-BRG",
    )
    assert pred_repeat.prediction_id == pred.prediction_id
    assert lineage_repeat.lineage_id == lineage.lineage_id
    assert snapshot_repeat.snapshot_id == snapshot.snapshot_id
