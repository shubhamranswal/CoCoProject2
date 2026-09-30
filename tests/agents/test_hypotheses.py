"""Unit tests verifying hypothesis evaluation and competing diagnosis logic."""

from datetime import datetime, timezone
import pytest

from domain.enums import FailureMode, Priority, Severity
from domain.models import Alert, Evidence, Machine
from agents.reliability.reasoner import (
    DeterministicInvestigationReasoner,
    InvestigationContext,
)


def test_deterministic_reasoner_evaluates_multiple_hypotheses():
    reasoner = DeterministicInvestigationReasoner()

    alert = Alert(
        alert_id="ALT-100",
        machine_id="M204",
        severity=Severity.CRITICAL,
        trigger_reason="Vibration and temperature runaway",
        risk_score=0.88,
        failure_mode=FailureMode.BEARING_DEGRADATION,
    )

    machine = Machine(
        machine_id="M204",
        machine_code="M204",
        name="M204 Conveyor Motor",
        line_id="LINE-B",
        model="DRV-5000",
    )

    evidence = [
        Evidence(
            evidence_id="E1",
            investigation_id="INV-TEST",
            evidence_type="TELEMETRY",
            source="sensors",
            metric="vibration_rms",
            observed_value=0.92,
            baseline_value=0.45,
            relationship="SUPPORTS",
            summary="Vibration high",
        ),
        Evidence(
            evidence_id="E2",
            investigation_id="INV-TEST",
            evidence_type="TELEMETRY",
            source="sensors",
            metric="temperature_mean",
            observed_value=85.0,
            baseline_value=58.5,
            relationship="SUPPORTS",
            summary="Temperature runaway",
        ),
        Evidence(
            evidence_id="E3",
            investigation_id="INV-TEST",
            evidence_type="TELEMETRY",
            source="sensors",
            metric="rpm_mean",
            observed_value=1750.0,
            baseline_value=1750.0,
            relationship="CONTRADICTS",
            is_contradictory=True,
            summary="Shaft speed steady",
        ),
        Evidence(
            evidence_id="E4",
            investigation_id="INV-TEST",
            evidence_type="FAILURE_HISTORY",
            source="history",
            metric="BEARING_DEGRADATION",
            observed_value="2025-04-08",
            relationship="SUPPORTS",
            summary="Prior bearing failure",
        ),
    ]

    ctx = InvestigationContext(
        investigation_id="INV-TEST",
        alert=alert,
        machine=machine,
        evidence=evidence,
    )

    res = reasoner.reason(ctx)

    assert len(res.hypotheses) == 3
    hyp_names = [h.hypothesis_name for h in res.hypotheses]
    assert "BEARING_DEGRADATION" in hyp_names
    assert "THERMAL_OVERLOAD" in hyp_names
    assert "MECHANICAL_MISALIGNMENT" in hyp_names

    bearing_h = next(h for h in res.hypotheses if h.hypothesis_name == "BEARING_DEGRADATION")
    assert bearing_h.status == "SUPPORTED"
    assert bearing_h.confidence >= 0.85
    assert len(bearing_h.supporting_evidence_ids) > 0
    assert len(bearing_h.contradicting_evidence_ids) > 0

    # Competing hypotheses should be marked REFUTED
    thermal_h = next(h for h in res.hypotheses if h.hypothesis_name == "THERMAL_OVERLOAD")
    assert thermal_h.status == "REFUTED"
    assert thermal_h.confidence < bearing_h.confidence
