"""Deterministic Risk Policy for Predictive Reliability Operations.

Enforces:
- Mathematical determinism: probability -> risk level
- No LLM involvement
- Immutable policy versioning
- Full traceability for prediction lineage
"""

from __future__ import annotations

from typing import Dict
from domain.enums import RiskLevel


class RiskPolicy:
    """Deterministic policy mapping failure probabilities to operational risk tiers."""

    POLICY_VERSION: str = "v1.0-canonical-thresholds"

    # Default canonical thresholds
    HIGH_THRESHOLD: float = 0.70
    CRITICAL_THRESHOLD: float = 0.85
    MEDIUM_THRESHOLD: float = 0.40

    def __init__(
        self,
        high_threshold: float = HIGH_THRESHOLD,
        critical_threshold: float = CRITICAL_THRESHOLD,
        medium_threshold: float = MEDIUM_THRESHOLD,
        version: str = POLICY_VERSION,
    ) -> None:
        self.high_threshold = high_threshold
        self.critical_threshold = critical_threshold
        self.medium_threshold = medium_threshold
        self.version = version

    def classify_canonical_tier(self, probability: float) -> str:
        """Classify probability into canonical 3-tier risk string ('high', 'medium', 'low')."""
        prob = max(0.0, min(1.0, float(probability)))
        if prob >= self.high_threshold:
            return "high"
        if prob >= self.medium_threshold:
            return "medium"
        return "low"

    def classify_risk_level(self, probability: float) -> RiskLevel:
        """Classify probability into domain RiskLevel enum (LOW, MEDIUM, HIGH, CRITICAL)."""
        prob = max(0.0, min(1.0, float(probability)))
        if prob >= self.critical_threshold:
            return RiskLevel.CRITICAL
        if prob >= self.high_threshold:
            return RiskLevel.HIGH
        if prob >= self.medium_threshold:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def get_threshold_summary(self) -> Dict[str, float]:
        return {
            "critical": self.critical_threshold,
            "high": self.high_threshold,
            "medium": self.medium_threshold,
            "low": 0.0,
        }
