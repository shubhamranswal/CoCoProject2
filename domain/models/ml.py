"""Machine Learning domain models for Milestone 3 Predictive Production Layer.

Enforces:
- Model Registry metadata and lifecycle (candidate, validated, active, retired)
- Time-based model evaluation split metrics
- Immutable prediction feature snapshots
- Complete auditable prediction lineage
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ModelRegistryRecord(BaseModel):
    """Registered ML model metadata and operational lifecycle state."""

    model_id: str
    model_name: str
    model_version: str
    algorithm: str
    training_dataset_version: str
    feature_version: str
    target_definition: str
    horizon_hours: int = 168  # 7 days
    training_start_date: Optional[date] = None
    training_end_date: Optional[date] = None
    validation_start_date: Optional[date] = None
    validation_end_date: Optional[date] = None
    test_start_date: Optional[date] = None
    test_end_date: Optional[date] = None
    auc_roc: Optional[float] = None
    pr_auc: Optional[float] = None
    precision_at_threshold: Optional[float] = None
    recall_at_threshold: Optional[float] = None
    f1_score: Optional[float] = None
    feature_count: int = 29
    parameters: Dict[str, Any] = Field(default_factory=dict)
    artifact_location: Optional[str] = None
    artifact_checksum: Optional[str] = None
    status: str = "candidate"  # candidate, validated, active, retired
    trained_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ModelEvaluationRecord(BaseModel):
    """Model evaluation metrics on a specific chronological data split."""

    evaluation_id: str
    model_id: str
    model_version: str
    split_name: str  # train, validation, test
    sample_count: int
    positive_count: int
    roc_auc: float
    pr_auc: float
    precision_score: float
    recall_score: float
    f1_score: float
    confusion_matrix: Dict[str, int] = Field(default_factory=dict)  # tp, fp, tn, fn
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PredictionFeatureSnapshot(BaseModel):
    """Immutable snapshot of the feature vector used to generate a specific prediction."""

    snapshot_id: str
    prediction_id: str
    machine_id: str
    feature_timestamp: datetime
    feature_version: str
    features: Dict[str, float] = Field(default_factory=dict)
    source_window_start: Optional[datetime] = None
    source_window_end: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PredictionLineage(BaseModel):
    """Complete provenance connecting a production prediction back to model and feature snapshot."""

    lineage_id: str
    prediction_id: str
    machine_id: str
    model_id: str
    model_version: str
    feature_version: str
    snapshot_id: str
    inference_timestamp: datetime
    failure_probability: float
    risk_level: str
    policy_version: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
