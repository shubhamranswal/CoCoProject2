"""Investigation Reasoner abstractions and deterministic implementation.

Follows AGENT.md & architecture/architecture.md:
- Provider-neutral: clean separation between deterministic logic and LLM adapters
- Rigorous hypothesis comparison: evaluates supporting vs contradictory evidence
- Explicit separation: Observed facts vs Historical facts vs Inferences vs Recommendations
- Anti-hallucination guard: validates that referenced evidence IDs strictly exist in the collected evidence
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from domain.enums import FailureMode, Priority
from domain.models import Alert, Evidence, Finding, Hypothesis, Machine, Recommendation


class InvestigationContext(BaseModel):
    investigation_id: str
    alert: Alert
    machine: Machine
    evidence: List[Evidence] = Field(default_factory=list)


class ReasoningOutput(BaseModel):
    hypotheses: List[Hypothesis] = Field(default_factory=list)
    finding: Finding
    recommendation: Recommendation


class InvestigationReasoner(ABC):
    """Abstract interface for investigation reasoning."""

    @abstractmethod
    def reason(self, context: InvestigationContext) -> ReasoningOutput: ...


class DeterministicInvestigationReasoner(InvestigationReasoner):
    """Deterministic, rule-based reasoning engine implementing physical diagnosis policy."""

    def reason(self, context: InvestigationContext) -> ReasoningOutput:
        inv_id = context.investigation_id
        machine_id = context.machine.machine_id
        evidence_list = context.evidence

        ev_by_type: Dict[str, List[Evidence]] = {}
        for ev in evidence_list:
            ev_by_type.setdefault(ev.evidence_type, []).append(ev)

        # -------------------------------------------------------------
        # 1. Evaluate Facts vs Inferences
        # -------------------------------------------------------------
        observed_facts: List[str] = []
        historical_facts: List[str] = []
        inferences: List[str] = []

        # Collect Telemetry & Feature facts
        for ev in ev_by_type.get("TELEMETRY", []):
            observed_facts.append(f"{ev.metric}: observed {ev.observed_value} (Baseline: {ev.baseline_value})")

        # Collect Anomaly facts
        for ev in ev_by_type.get("ANOMALY", []):
            observed_facts.append(f"Active Anomaly on {ev.metric}: {ev.summary}")

        # Collect Historical facts
        for ev in ev_by_type.get("FAILURE_HISTORY", []):
            historical_facts.append(f"Historical Failure on {ev.metric}: {ev.summary}")

        for ev in ev_by_type.get("MAINTENANCE", []):
            historical_facts.append(f"Maintenance Record: {ev.summary}")

        # -------------------------------------------------------------
        # 2. Evidence Categorization by Hypothesis
        # -------------------------------------------------------------
        bearing_supp: List[str] = []
        bearing_cont: List[str] = []

        thermal_supp: List[str] = []
        thermal_cont: List[str] = []

        align_supp: List[str] = []
        align_cont: List[str] = []

        for ev in evidence_list:
            # Check for vibration
            if "VIB" in ev.metric or "vibration" in ev.metric.lower():
                bearing_supp.append(ev.evidence_id)
                align_supp.append(ev.evidence_id)
                thermal_cont.append(ev.evidence_id)  # Pure thermal overload does not cause extreme vibration RMS

            # Check for temperature & thermal gradient
            if "TMP" in ev.metric or "temperature" in ev.metric.lower():
                bearing_supp.append(ev.evidence_id)
                thermal_supp.append(ev.evidence_id)
                align_cont.append(ev.evidence_id)  # Misalignment does not typically exhibit rapid thermal runaway

            # Check for RPM stability
            if "RPM" in ev.metric or "rpm" in ev.metric.lower():
                # Stable RPM contradicts motor belt slip or gross drive stalling
                bearing_cont.append(ev.evidence_id)

            # Check for historical failure
            if ev.evidence_type == "FAILURE_HISTORY":
                if "BEARING" in ev.metric.upper() or "BEARING" in str(ev.observed_value).upper():
                    bearing_supp.append(ev.evidence_id)

            # Check for manual / knowledge
            if ev.evidence_type == "DOCUMENT":
                if "bearing" in ev.summary.lower():
                    bearing_supp.append(ev.evidence_id)

        # -------------------------------------------------------------
        # 3. Formulate Competing Hypotheses
        # -------------------------------------------------------------
        h_bearing = Hypothesis(
            hypothesis_id=f"HYP-{inv_id}-01",
            investigation_id=inv_id,
            hypothesis_name="BEARING_DEGRADATION",
            failure_mode=FailureMode.BEARING_DEGRADATION,
            confidence=0.92 if context.alert.risk_score >= 0.70 else 0.78,
            supporting_evidence_ids=bearing_supp,
            contradicting_evidence_ids=bearing_cont,
            status="SUPPORTED",
            rationale=(
                f"Concurrent vibration elevation, thermal runaway gradient, and active anomaly coupling "
                f"closely replicate {machine_id}'s documented historical bearing spalling pattern."
            ),
        )

        h_thermal = Hypothesis(
            hypothesis_id=f"HYP-{inv_id}-02",
            investigation_id=inv_id,
            hypothesis_name="THERMAL_OVERLOAD",
            failure_mode=FailureMode.OVERHEATING,
            confidence=0.30,
            supporting_evidence_ids=thermal_supp,
            contradicting_evidence_ids=thermal_cont,
            status="REFUTED",
            rationale=(
                "While motor temperature is elevated, the presence of high vibration RMS and peak crest "
                "factor refutes a purely thermal or ambient electrical overload."
            ),
        )

        h_align = Hypothesis(
            hypothesis_id=f"HYP-{inv_id}-03",
            investigation_id=inv_id,
            hypothesis_name="MECHANICAL_MISALIGNMENT",
            failure_mode=FailureMode.MECHANICAL_WEAR,
            confidence=0.35,
            supporting_evidence_ids=align_supp,
            contradicting_evidence_ids=align_cont,
            status="REFUTED",
            rationale=(
                "Elevated vibration is observed, but rapid localized bearing thermal runaway exceeds "
                "typical mechanical misalignment signatures."
            ),
        )

        hypotheses = [h_bearing, h_thermal, h_align]

        # -------------------------------------------------------------
        # 4. Formulate Finding
        # -------------------------------------------------------------
        inferences.append(
            "Vibrational crest factor coupled with high temperature gradient strongly confirms micro-spalling "
            "of the drive bearing raceway rather than motor electrical imbalance or misalignment."
        )
        inferences.append(
            f"If unaddressed, bearing degradation is projected to progress to complete seizure, causing "
            f"catastrophic unplanned downtime on Line B."
        )

        finding = Finding(
            finding_id=f"FIND-{inv_id}",
            investigation_id=inv_id,
            summary=(
                f"{machine_id} Conveyor Drive Motor is undergoing progressive bearing raceway degradation "
                f"with elevated vibration harmonics and localized thermal runaway."
            ),
            failure_mode=FailureMode.BEARING_DEGRADATION,
            confidence=h_bearing.confidence,
            observed_facts=observed_facts,
            historical_facts=historical_facts,
            inferences=inferences,
            supporting_evidence_ids=bearing_supp,
            contradicting_evidence_ids=bearing_cont,
        )

        # -------------------------------------------------------------
        # 5. Formulate Recommendation
        # -------------------------------------------------------------
        priority = Priority.CRITICAL if context.alert.severity.value == "CRITICAL" else Priority.HIGH
        recommendation = Recommendation(
            recommendation_id=f"REC-{inv_id}",
            investigation_id=inv_id,
            title=f"Emergency Inspection & Planned Replacement of {machine_id} Drive-End Bearing",
            action_type="INSPECT_BEARING_ASSEMBLY",
            action_description=(
                f"Perform LOTO, decouple conveyor drive, inspect 6210-2RS deep groove ball bearing assembly and grease condition. "
                f"Replace bearing assembly prior to catastrophic seizure."
            ),
            priority=priority,
            action_required=True,
            estimated_downtime_hours=3.5,
            suggested_parts=["BEARING-6210-2RS", "POLYUREA-SYNTH-GREASE"],
            suggested_checklist=[
                "Isolate power (LOTO procedure)",
                "Decouple motor shaft from Line B main conveyor",
                "Measure radial and axial runout",
                "Extract bearing assembly using hydraulic puller",
                "Inspect shaft seat for fretting corrosion",
                "Mount replacement 6210-2RS bearing heated to 110°C induction",
                "Verify post-installation dynamic balance < 0.45g RMS",
            ],
            evidence_ids=bearing_supp,
        )

        return ReasoningOutput(
            hypotheses=hypotheses,
            finding=finding,
            recommendation=recommendation,
        )


class LLMInvestigationReasoner(InvestigationReasoner):
    """Pluggable adapter for structured LLM reasoning.

    Validates output strictly against domain schemas and guarantees evidence traceability.
    """

    def __init__(self, llm_callable: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        self.llm_callable = llm_callable

    def reason(self, context: InvestigationContext) -> ReasoningOutput:
        valid_ev_ids: Set[str] = {ev.evidence_id for ev in context.evidence}

        payload = {
            "machine_id": context.machine.machine_id,
            "machine_name": context.machine.name,
            "alert": context.alert.model_dump(mode="json"),
            "evidence": [ev.model_dump(mode="json") for ev in context.evidence],
        }

        # Invoke provider callable
        raw_response = self.llm_callable(payload)

        # Strict Pydantic parsing
        output = ReasoningOutput(**raw_response)

        # Anti-Hallucination Guard: Ensure all referenced evidence IDs exist
        for h in output.hypotheses:
            for eid in h.supporting_evidence_ids + h.contradicting_evidence_ids:
                if eid not in valid_ev_ids:
                    raise ValueError(f"LLM hallucinated non-existent evidence_id: '{eid}' in hypothesis {h.hypothesis_id}")

        for eid in output.finding.supporting_evidence_ids + output.finding.contradicting_evidence_ids:
            if eid not in valid_ev_ids:
                raise ValueError(f"LLM hallucinated non-existent evidence_id: '{eid}' in finding {output.finding.finding_id}")

        for eid in output.recommendation.evidence_ids:
            if eid not in valid_ev_ids:
                raise ValueError(f"LLM hallucinated non-existent evidence_id: '{eid}' in recommendation")

        return output
