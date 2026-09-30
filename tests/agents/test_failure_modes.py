"""Tests verifying graceful failure handling and anti-hallucination guards."""

from datetime import datetime, timezone
import pytest

from domain.enums import AlertStatus, FailureMode, InvestigationStatus, Priority, Severity
from domain.models import Alert, Evidence, Finding, Hypothesis, Machine, Recommendation
from repositories.memory.memory_repository import InMemoryRepository
from agents.reliability.agent import ReliabilityInvestigationAgent
from agents.reliability.reasoner import (
    InvestigationContext,
    LLMInvestigationReasoner,
    ReasoningOutput,
)


def test_investigation_non_existent_alert_raises_gracefully():
    repo = InMemoryRepository()
    agent = ReliabilityInvestigationAgent(repository=repo)

    with pytest.raises(ValueError, match="does not exist"):
        agent.investigate_alert("ALT-NON-EXISTENT")


def test_investigation_already_resolved_alert_skips_processing():
    repo = InMemoryRepository()
    agent = ReliabilityInvestigationAgent(repository=repo)

    alert = Alert(
        alert_id="ALT-RESOLVED",
        machine_id="M204",
        severity=Severity.LOW,
        status=AlertStatus.RESOLVED,
        trigger_reason="Previously resolved",
        risk_score=0.10,
    )
    repo.create_alert(alert)

    res = agent.investigate_alert("ALT-RESOLVED")
    assert res.investigation.status == InvestigationStatus.CLOSED
    assert len(res.evidence) == 0
    assert res.approval is None


def test_investigation_graceful_with_unseeded_clean_machine():
    repo = InMemoryRepository(seed=False)
    agent = ReliabilityInvestigationAgent(repository=repo)

    # Machine with no telemetry, no history, no manual
    mach = Machine(
        machine_id="M999",
        machine_code="M999",
        name="Experimental Motor",
        line_id="LINE-C",
        model="DRV-UNKNOWN",
    )
    repo._machines["M999"] = mach

    alert = Alert(
        alert_id="ALT-M999-01",
        machine_id="M999",
        severity=Severity.HIGH,
        trigger_reason="Spike detected",
        risk_score=0.75,
    )
    repo.create_alert(alert)

    res = agent.investigate_alert("ALT-M999-01")
    # Investigation completes without unhandled exceptions
    assert res.investigation is not None
    assert res.finding is not None
    assert res.recommendation is not None


def test_llm_reasoner_anti_hallucination_guard():
    # Mock LLM that returns a hallucinated evidence ID not in context
    def mock_hallucinating_llm(payload):
        return {
            "hypotheses": [
                {
                    "hypothesis_id": "H1",
                    "investigation_id": "INV-1",
                    "hypothesis_name": "BEARING_DEGRADATION",
                    "failure_mode": "BEARING_DEGRADATION",
                    "confidence": 0.95,
                    "supporting_evidence_ids": ["E1", "E999_HALLUCINATED"],  # Hallucinated!
                    "contradicting_evidence_ids": [],
                    "status": "SUPPORTED",
                    "rationale": "Made up evidence",
                }
            ],
            "finding": {
                "finding_id": "F1",
                "investigation_id": "INV-1",
                "summary": "Hallucinated finding",
                "failure_mode": "BEARING_DEGRADATION",
                "confidence": 0.95,
                "observed_facts": [],
                "historical_facts": [],
                "inferences": [],
                "supporting_evidence_ids": ["E1"],
                "contradicting_evidence_ids": [],
            },
            "recommendation": {
                "recommendation_id": "R1",
                "investigation_id": "INV-1",
                "title": "Repair",
                "action_type": "INSPECT_BEARING_ASSEMBLY",
                "action_description": "Fix it",
                "priority": "HIGH",
                "action_required": True,
                "estimated_downtime_hours": 1.0,
                "suggested_parts": [],
                "suggested_checklist": [],
                "evidence_ids": ["E1"],
            },
        }

    reasoner = LLMInvestigationReasoner(mock_hallucinating_llm)

    ctx = InvestigationContext(
        investigation_id="INV-1",
        alert=Alert(
            alert_id="A1",
            machine_id="M204",
            severity=Severity.HIGH,
            trigger_reason="Test",
            risk_score=0.8,
        ),
        machine=Machine(machine_id="M204", machine_code="M204", name="Motor", line_id="LINE-B"),
        evidence=[
            Evidence(
                evidence_id="E1",
                investigation_id="INV-1",
                evidence_type="TELEMETRY",
                source="test",
                metric="vibration",
                observed_value=0.9,
                relationship="SUPPORTS",
                summary="Test evidence",
            )
        ],
    )

    with pytest.raises(ValueError, match="LLM hallucinated non-existent evidence_id"):
        reasoner.reason(ctx)
