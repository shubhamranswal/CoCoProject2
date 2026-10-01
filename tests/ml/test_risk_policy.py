"""Unit tests for deterministic RiskPolicy."""

import pytest
from domain.enums import RiskLevel
from ml.inference.risk_policy import RiskPolicy


def test_deterministic_risk_mapping():
    policy = RiskPolicy()

    # Low risk
    assert policy.classify_canonical_tier(0.0) == "low"
    assert policy.classify_canonical_tier(0.25) == "low"
    assert policy.classify_canonical_tier(0.399) == "low"
    assert policy.classify_risk_level(0.25) == RiskLevel.LOW

    # Medium risk
    assert policy.classify_canonical_tier(0.40) == "medium"
    assert policy.classify_canonical_tier(0.55) == "medium"
    assert policy.classify_canonical_tier(0.699) == "medium"
    assert policy.classify_risk_level(0.55) == RiskLevel.MEDIUM

    # High / Critical risk
    assert policy.classify_canonical_tier(0.70) == "high"
    assert policy.classify_canonical_tier(0.80) == "high"
    assert policy.classify_canonical_tier(0.95) == "high"
    assert policy.classify_risk_level(0.75) == RiskLevel.HIGH
    assert policy.classify_risk_level(0.95) == RiskLevel.CRITICAL


def test_risk_policy_immutability_and_version():
    policy = RiskPolicy()
    assert policy.version == "v1.0-canonical-thresholds"
    summary = policy.get_threshold_summary()
    assert summary["high"] == 0.70
    assert summary["medium"] == 0.40
    assert summary["critical"] == 0.85


def test_clamped_extremes():
    policy = RiskPolicy()
    assert policy.classify_canonical_tier(-0.5) == "low"
    assert policy.classify_canonical_tier(1.5) == "high"
    assert policy.classify_risk_level(2.0) == RiskLevel.CRITICAL
