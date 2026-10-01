"""Unit tests for deterministic RiskPolicy."""

import pytest
from domain.enums import RiskLevel
from ml.inference.risk_policy import RiskPolicy


def test_deterministic_risk_mapping():
    policy = RiskPolicy()

    # Low risk
    assert policy.classify_canonical_tier(0.0) == "LOW"
    assert policy.classify_canonical_tier(0.25) == "LOW"
    assert policy.classify_canonical_tier(0.399) == "LOW"
    assert policy.classify_risk_level(0.25) == RiskLevel.LOW

    # Medium risk
    assert policy.classify_canonical_tier(0.40) == "MEDIUM"
    assert policy.classify_canonical_tier(0.55) == "MEDIUM"
    assert policy.classify_canonical_tier(0.699) == "MEDIUM"
    assert policy.classify_risk_level(0.55) == RiskLevel.MEDIUM

    # High risk
    assert policy.classify_canonical_tier(0.70) == "HIGH"
    assert policy.classify_canonical_tier(0.80) == "HIGH"
    assert policy.classify_risk_level(0.75) == RiskLevel.HIGH

    # Critical risk
    assert policy.classify_canonical_tier(0.85) == "CRITICAL"
    assert policy.classify_canonical_tier(0.95) == "CRITICAL"
    assert policy.classify_risk_level(0.95) == RiskLevel.CRITICAL


def test_map_legacy_risk_level():
    policy = RiskPolicy()
    assert policy.map_legacy_risk_level("high") == RiskLevel.HIGH
    assert policy.map_legacy_risk_level("HIGH") == RiskLevel.HIGH
    assert policy.map_legacy_risk_level("critical") == RiskLevel.CRITICAL
    assert policy.map_legacy_risk_level("CRITICAL") == RiskLevel.CRITICAL
    assert policy.map_legacy_risk_level("medium") == RiskLevel.MEDIUM
    assert policy.map_legacy_risk_level("low") == RiskLevel.LOW


def test_risk_policy_immutability_and_version():
    policy = RiskPolicy()
    assert policy.version == "v1.0-canonical-thresholds"
    summary = policy.get_threshold_summary()
    assert summary["high"] == 0.70
    assert summary["medium"] == 0.40
    assert summary["critical"] == 0.85


def test_clamped_extremes():
    policy = RiskPolicy()
    assert policy.classify_canonical_tier(-0.5) == "LOW"
    assert policy.classify_canonical_tier(1.5) == "CRITICAL"
    assert policy.classify_risk_level(2.0) == RiskLevel.CRITICAL
