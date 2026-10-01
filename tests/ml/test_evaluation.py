"""Tests for model evaluation metrics and reports."""

import pytest
from domain.models import MLFailurePrediction
from ml.evaluation.evaluator import evaluate_predictions, EvaluationReport


def test_evaluator_metrics():
    # 4 predictions: 2 TP, 1 FP, 1 TN, 0 FN
    preds = [
        MLFailurePrediction(
            prediction_id="P1", machine_id="M1", failure_probability=0.85,
            model_name="test", model_version="1.0", training_dataset_version="v1", feature_schema_version="v1"
        ),
        MLFailurePrediction(
            prediction_id="P2", machine_id="M2", failure_probability=0.75,
            model_name="test", model_version="1.0", training_dataset_version="v1", feature_schema_version="v1"
        ),
        MLFailurePrediction(
            prediction_id="P3", machine_id="M3", failure_probability=0.60,
            model_name="test", model_version="1.0", training_dataset_version="v1", feature_schema_version="v1"
        ),
        MLFailurePrediction(
            prediction_id="P4", machine_id="M4", failure_probability=0.10,
            model_name="test", model_version="1.0", training_dataset_version="v1", feature_schema_version="v1"
        ),
    ]
    labels = [True, True, False, False]

    report = evaluate_predictions(preds, labels, threshold=0.50)
    assert isinstance(report, EvaluationReport)
    assert report.total_samples == 4
    assert report.true_positives == 2
    assert report.false_positives == 1
    assert report.true_negatives == 1
    assert report.false_negatives == 0
    assert report.precision == pytest.approx(2 / 3, 0.01)
    assert report.recall == 1.0
    assert report.roc_auc > 0.8
    assert len(report.error_analysis) == 1
    assert report.error_analysis[0]["type"] == "FALSE_POSITIVE"
