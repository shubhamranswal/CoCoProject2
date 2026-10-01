"""Integration tests for canonical model training pipeline, chronological splits, and artifact persistence."""

import os
from pathlib import Path
import pytest

from domain.models import ModelRegistryRecord, ModelEvaluationRecord
from ml.training.train_canonical_model import train_canonical_model
from repositories.memory.memory_repository import InMemoryRepository


@pytest.mark.skipif(
    not os.path.exists(r"C:\Users\shubh\Desktop\oee_v2\sensor.csv"),
    reason="Canonical dataset directory C:\\Users\\shubh\\Desktop\\oee_v2 not accessible",
)
def test_train_canonical_model_end_to_end(tmp_path: Path):
    repo = InMemoryRepository(seed=False)

    reg_record, eval_records, model = train_canonical_model(
        data_dir=r"C:\Users\shubh\Desktop\oee_v2",
        artifacts_dir=str(tmp_path),
        model_id="hgb_failure_7d_test",
        model_name="Canonical 7-Day Failure Predictor Test",
        model_version="1.0.0",
        dataset_version="v2026.03-canonical",
        promote_to_active=True,
        ml_repo=repo,
    )

    # 1. Verify ModelRegistryRecord
    assert reg_record.model_id == "hgb_failure_7d_test"
    assert reg_record.algorithm == "HistGradientBoostingClassifier"
    assert reg_record.feature_count == 29
    assert reg_record.horizon_hours == 168
    assert reg_record.status == "active"
    assert reg_record.auc_roc is not None
    assert reg_record.auc_roc > 0.70, f"Expected AUC > 0.70, got {reg_record.auc_roc}"
    assert reg_record.artifact_checksum is not None
    assert len(reg_record.artifact_checksum) == 64  # SHA-256 hex length

    # Verify chronological split boundaries
    assert reg_record.training_end_date is not None
    assert reg_record.test_start_date is not None
    # Training end must precede test start by at least 7 days buffer
    assert (reg_record.test_start_date - reg_record.training_end_date).days >= 7

    # 2. Verify ModelEvaluationRecords
    assert len(eval_records) == 2
    split_names = [e.split_name for e in eval_records]
    assert "train" in split_names
    assert "test" in split_names

    test_eval = next(e for e in eval_records if e.split_name == "test")
    assert test_eval.sample_count > 0
    assert test_eval.positive_count > 0
    assert test_eval.roc_auc > 0.70

    # 3. Verify Artifact Persistence
    artifact_file = Path(reg_record.artifact_location)
    assert artifact_file.exists(), f"Artifact file {artifact_file} must exist"
    assert artifact_file.stat().st_size > 1000

    # 4. Verify Repository Registration
    active_in_repo = repo.get_active_model()
    assert active_in_repo is not None
    assert active_in_repo.model_id == "hgb_failure_7d_test"
    repo_evals = repo.list_evaluations("hgb_failure_7d_test")
    assert len(repo_evals) == 2
