"""Evaluation metrics for predictive reliability models.

Calculates:
- Precision, Recall, F1
- ROC-AUC (Wilcoxon-Mann-Whitney rank sum / trapezoidal integration)
- Confusion Matrix (TP, FP, TN, FN)
- False Alarm Rate & Miss Rate
- Error case breakdown
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from domain.models import MLFailurePrediction


@dataclass
class EvaluationReport:
    total_samples: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    roc_auc: float
    false_alarm_rate: float
    miss_rate: float
    threshold_used: float
    error_analysis: List[Dict[str, str]] = field(default_factory=list)


def _compute_roc_auc(scores: List[float], labels: List[bool]) -> float:
    """Compute Area Under ROC Curve via Mann-Whitney U test statistic."""
    pos_scores = [s for s, y in zip(scores, labels) if y]
    neg_scores = [s for s, y in zip(scores, labels) if not y]

    n_pos = len(pos_scores)
    n_neg = len(neg_scores)

    if n_pos == 0 or n_neg == 0:
        return 0.5  # Undefined / uniform baseline

    # Count pairs where pos > neg (0.5 for ties)
    wins = 0.0
    for p in pos_scores:
        for n in neg_scores:
            if p > n:
                wins += 1.0
            elif p == n:
                wins += 0.5

    return round(wins / (n_pos * n_neg), 4)


def evaluate_predictions(
    predictions: List[MLFailurePrediction],
    ground_truth: List[bool],
    threshold: float = 0.50,
) -> EvaluationReport:
    """Evaluate a set of ML failure predictions against actual ground-truth binary labels."""
    if len(predictions) != len(ground_truth):
        raise ValueError(
            f"Mismatched lengths: predictions ({len(predictions)}) vs ground_truth ({len(ground_truth)})"
        )

    n = len(predictions)
    if n == 0:
        return EvaluationReport(
            total_samples=0,
            true_positives=0,
            false_positives=0,
            true_negatives=0,
            false_negatives=0,
            precision=0.0,
            recall=0.0,
            f1_score=0.0,
            roc_auc=0.5,
            false_alarm_rate=0.0,
            miss_rate=0.0,
            threshold_used=threshold,
        )

    tp = fp = tn = fn = 0
    scores: List[float] = []
    error_cases: List[Dict[str, str]] = []

    for pred, actual in zip(predictions, ground_truth):
        p_val = pred.failure_probability
        scores.append(p_val)
        predicted_positive = p_val >= threshold

        if predicted_positive and actual:
            tp += 1
        elif predicted_positive and not actual:
            fp += 1
            error_cases.append({
                "type": "FALSE_POSITIVE",
                "prediction_id": pred.prediction_id,
                "machine_id": pred.machine_id,
                "prob": str(p_val),
                "reason": "Model predicted failure above threshold, but component operated normally.",
            })
        elif not predicted_positive and actual:
            fn += 1
            error_cases.append({
                "type": "FALSE_NEGATIVE",
                "prediction_id": pred.prediction_id,
                "machine_id": pred.machine_id,
                "prob": str(p_val),
                "reason": "Model failed to trigger warning before physical failure occurred.",
            })
        else:
            tn += 1

    precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
    recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
    f1 = round(2 * (precision * recall) / (precision + recall), 4) if (precision + recall) > 0 else 0.0
    far = round(fp / (fp + tn), 4) if (fp + tn) > 0 else 0.0
    miss = round(fn / (fn + tp), 4) if (fn + tp) > 0 else 0.0
    auc = _compute_roc_auc(scores, ground_truth)

    return EvaluationReport(
        total_samples=n,
        true_positives=tp,
        false_positives=fp,
        true_negatives=tn,
        false_negatives=fn,
        precision=precision,
        recall=recall,
        f1_score=f1,
        roc_auc=auc,
        false_alarm_rate=far,
        miss_rate=miss,
        threshold_used=threshold,
        error_analysis=error_cases,
    )
