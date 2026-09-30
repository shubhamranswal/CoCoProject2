"""Unit tests verifying evidence generation, fact vs inference separation, and traceability."""

from datetime import datetime, timezone
import pytest

from domain.models import Evidence, Finding, Hypothesis, Recommendation
from domain.enums import FailureMode, Priority


def test_evidence_structure_and_contradictory_flag():
    ev_supp = Evidence(
        evidence_id="E1",
        investigation_id="INV-01",
        evidence_type="TELEMETRY",
        source="ml.features.FeatureExtractor",
        metric="vibration_rms",
        observed_value=0.88,
        baseline_value=0.45,
        relationship="SUPPORTS",
        is_contradictory=False,
        observed_fact="Vibration RMS elevated by +95%",
        summary="Vibration RMS reached 0.88g.",
    )

    ev_contra = Evidence(
        evidence_id="E2",
        investigation_id="INV-01",
        evidence_type="TELEMETRY",
        source="ml.features.FeatureExtractor",
        metric="rpm_mean",
        observed_value=1750.0,
        baseline_value=1750.0,
        relationship="CONTRADICTS",
        is_contradictory=True,
        observed_fact="Shaft speed remains normal at 1750 RPM",
        summary="Shaft speed shows no slip or stall.",
    )

    assert ev_supp.relationship == "SUPPORTS"
    assert ev_supp.is_contradictory is False

    assert ev_contra.relationship == "CONTRADICTS"
    assert ev_contra.is_contradictory is True


def test_finding_separates_facts_and_inferences():
    finding = Finding(
        finding_id="FIND-01",
        investigation_id="INV-01",
        summary="Bearing degradation identified.",
        failure_mode=FailureMode.BEARING_DEGRADATION,
        confidence=0.92,
        observed_facts=[
            "Vibration RMS reached 0.918 g (baseline 0.45 g)",
            "Temperature reached 84.0 °C (baseline 58.5 °C)",
        ],
        historical_facts=[
            "M204 suffered bearing spalling failure on 2025-04-08",
        ],
        inferences=[
            "Vibration harmonic coupled with thermal gradient indicates inner raceway fatigue.",
        ],
        supporting_evidence_ids=["E1", "E3"],
        contradicting_evidence_ids=["E2"],
    )

    assert len(finding.observed_facts) == 2
    assert len(finding.historical_facts) == 1
    assert len(finding.inferences) == 1
    assert "E1" in finding.supporting_evidence_ids
    assert "E2" in finding.contradicting_evidence_ids
