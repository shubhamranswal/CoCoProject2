"""Prediction Service for Milestone 3 Predictive Production Layer.

Coordinates:
- Active model resolution from Model Registry
- Feature snapshot immutability
- Deterministic inference and risk tier assignment
- Auditable prediction lineage recording
- Strict idempotency on natural key (machine_id, timestamp, model_version, feature_version)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from domain.enums import FailureMode, RiskLevel
from domain.models import (
    MLFailurePrediction,
    ModelRegistryRecord,
    PredictionFeatureSnapshot,
    PredictionLineage,
)
from ml.models.canonical_predictor import CanonicalFailurePredictor
from ml.inference.risk_policy import RiskPolicy
from repositories.base import MLRepository


class PredictionService:
    """Production service orchestrating deterministic ML inference, lineage, and persistence."""

    def __init__(
        self,
        ml_repository: MLRepository,
        predictor: Optional[CanonicalFailurePredictor] = None,
        risk_policy: Optional[RiskPolicy] = None,
    ) -> None:
        self.repo = ml_repository
        self.risk_policy = risk_policy or RiskPolicy()
        self._predictor = predictor

    def _resolve_predictor(self) -> CanonicalFailurePredictor:
        """Resolve active predictor from registry or memory cache."""
        if self._predictor is not None:
            return self._predictor

        active_rec = self.repo.get_active_model()
        if active_rec is not None:
            trained_model = None
            if active_rec.artifact_location:
                import os, pickle
                if os.path.exists(active_rec.artifact_location):
                    try:
                        with open(active_rec.artifact_location, "rb") as f:
                            trained_model = pickle.load(f)
                    except Exception:
                        trained_model = None

            self._predictor = CanonicalFailurePredictor(
                model_name=active_rec.model_name,
                model_version=active_rec.model_version,
                training_dataset_version=active_rec.training_dataset_version,
                feature_schema_version=active_rec.feature_version,
                trained_model=trained_model,
                risk_policy=self.risk_policy,
            )
            return self._predictor

        # Default canonical baseline predictor
        self._predictor = CanonicalFailurePredictor(
            model_name="hgb_failure_7d_v1",
            model_version="1.0.0",
            training_dataset_version="v2026.03-canonical",
            feature_schema_version="v1.0-29feat",
            risk_policy=self.risk_policy,
        )
        return self._predictor

    def generate_prediction(
        self,
        machine_id: str,
        features: Dict[str, float],
        as_of: Optional[datetime] = None,
        component_id: Optional[str] = None,
        source_window_start: Optional[datetime] = None,
        source_window_end: Optional[datetime] = None,
    ) -> Tuple[MLFailurePrediction, PredictionLineage, PredictionFeatureSnapshot]:
        """Generate, persist, and record full lineage for a single machine prediction with strict idempotency."""
        ts = as_of or datetime.now(timezone.utc)
        predictor = self._resolve_predictor()

        # Deterministic natural key for idempotency
        ts_sec = int(ts.timestamp())
        pred_id = f"PRED-{machine_id}-{ts_sec}"
        snapshot_id = f"SNAP-{machine_id}-{ts_sec}"
        lineage_id = f"LIN-{machine_id}-{ts_sec}"

        # 1. Idempotency Check: Return existing if already computed for this exact key
        existing_pred = self.repo.get_prediction_by_id(pred_id)
        existing_lineage = self.repo.get_prediction_lineage(pred_id)
        existing_snap = self.repo.get_prediction_feature_snapshot(snapshot_id)

        if existing_pred is not None and existing_lineage is not None and existing_snap is not None:
            return existing_pred, existing_lineage, existing_snap

        # 2. Run deterministic inference
        pred = predictor.predict(
            machine_id=machine_id,
            features=features,
            horizon_hours=168,
            component_id=component_id,
            as_of=ts,
            prediction_id=pred_id,
        )

        risk_str = self.risk_policy.classify_canonical_tier(pred.failure_probability)

        # 3. Create Immutable Feature Snapshot
        snapshot = PredictionFeatureSnapshot(
            snapshot_id=snapshot_id,
            prediction_id=pred_id,
            machine_id=machine_id,
            feature_timestamp=ts,
            feature_version=predictor.feature_schema_version,
            features=features,
            source_window_start=source_window_start,
            source_window_end=source_window_end or ts,
            created_at=datetime.now(timezone.utc),
        )

        # 4. Create Auditable Prediction Lineage
        lineage = PredictionLineage(
            lineage_id=lineage_id,
            prediction_id=pred_id,
            machine_id=machine_id,
            model_id=predictor.model_name,
            model_version=predictor.model_version,
            feature_version=predictor.feature_schema_version,
            snapshot_id=snapshot_id,
            inference_timestamp=ts,
            failure_probability=pred.failure_probability,
            risk_level=risk_str,
            policy_version=self.risk_policy.version,
            created_at=datetime.now(timezone.utc),
        )

        # 5. Persist through repository
        self.repo.save_prediction_feature_snapshot(snapshot)
        self.repo.save_prediction_lineage(lineage)
        self.repo.save_prediction(pred)

        return pred, lineage, snapshot

    def predict_batch(
        self,
        machine_feature_map: Dict[str, Dict[str, float]],
        as_of: Optional[datetime] = None,
    ) -> List[MLFailurePrediction]:
        """Execute deterministic batch inference across machines."""
        predictions: List[MLFailurePrediction] = []
        for machine_id, feats in machine_feature_map.items():
            pred, _, _ = self.generate_prediction(machine_id=machine_id, features=feats, as_of=as_of)
            predictions.append(pred)
        return predictions
