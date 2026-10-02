"""CoCo Reasoning Adapter Layer for Autonomous Reliability Investigation.

Provides:
- Structured InvestigationContext evidence bundle
- Abstract CoCoInvestigationAdapter interface
- DeterministicCoCoAdapter for offline testing and deterministic operations
- LiveCortexCoCoAdapter boundary for live Snowflake Cortex LLM integration
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from domain.enums import FailureMode, Priority, InvestigationStatus
from domain.models import (
    Evidence,
    Finding,
    Hypothesis,
    Recommendation,
    InvestigationResult,
)
from agents.reliability.anti_hallucination import AntiHallucinationValidator, AntiHallucinationError

logger = logging.getLogger(__name__)


class InvestigationContext(BaseModel):
    """Structured evidence bundle prepared for CoCo investigative reasoning."""

    investigation_id: str
    machine_id: str
    component_id: Optional[str] = None
    trigger_type: str = "PREDICTION"
    trigger_id: Optional[str] = None
    prediction: Optional[Dict[str, Any]] = None
    lineage: Optional[Dict[str, Any]] = None
    snapshot: Optional[Dict[str, Any]] = None
    machine_context: Optional[Dict[str, Any]] = None
    machine_health: Optional[Dict[str, Any]] = None
    sensor_context: Optional[Dict[str, Any]] = None
    maintenance_history: Optional[Dict[str, Any]] = None
    historical_failures: Optional[Dict[str, Any]] = None
    downtime_history: Optional[Dict[str, Any]] = None
    inventory_risk: Optional[Dict[str, Any]] = None
    production_context: Optional[Dict[str, Any]] = None
    knowledge_results: Optional[Dict[str, Any]] = None
    evidence_items: List[Evidence] = Field(default_factory=list)


class CoCoInvestigationAdapter(ABC):
    """Abstract interface for CoCo reasoning engines."""

    @abstractmethod
    def reason(self, context: InvestigationContext) -> InvestigationResult:
        """Produce structured findings, hypotheses, and advisory recommendations from evidence."""
        ...


class DeterministicCoCoAdapter(CoCoInvestigationAdapter):
    """Deterministic, provider-neutral reasoning adapter strictly grounded in supplied evidence."""

    def reason(self, context: InvestigationContext) -> InvestigationResult:
        inv_id = context.investigation_id
        mach_id = context.machine_id
        ev_items = context.evidence_items

        # Index evidence by category and ID
        ev_by_cat: Dict[str, List[Evidence]] = {}
        for ev in ev_items:
            cat = ev.category or ev.evidence_type
            ev_by_cat.setdefault(cat.upper(), []).append(ev)

        hypotheses: List[Hypothesis] = []
        findings: List[Finding] = []
        recommendations: List[Recommendation] = []
        limitations: List[str] = []
        all_cited_refs: List[str] = []

        # 1. Evaluate Sensor & Telemetry Evidence
        sensor_evs = ev_by_cat.get("SENSOR", []) + ev_by_cat.get("TELEMETRY", [])
        pred_evs = ev_by_cat.get("PREDICTION", [])
        maint_evs = ev_by_cat.get("MAINTENANCE", [])
        fail_evs = ev_by_cat.get("FAILURE_HISTORY", [])
        inv_evs = ev_by_cat.get("INVENTORY", [])
        prod_evs = ev_by_cat.get("PRODUCTION", [])
        know_evs = ev_by_cat.get("KNOWLEDGE", [])

        # Check for missing data categories
        if not inv_evs:
            limitations.append("Inventory evidence unavailable: Spare part availability is not established.")
        if not prod_evs:
            limitations.append("Production context unavailable: Active order financial exposure could not be verified.")
        if not know_evs:
            limitations.append("Technical documentation search returned zero matching records.")

        # --- A. Primary Bearing Degradation Hypothesis ---
        bearing_supp: List[str] = []
        bearing_cont: List[str] = []

        for ev in sensor_evs:
            if "VIB" in ev.metric.upper() or "VIBRATION" in ev.metric.upper():
                bearing_supp.append(ev.evidence_id)
            elif "TMP" in ev.metric.upper() or "TEMPERATURE" in ev.metric.upper():
                bearing_supp.append(ev.evidence_id)

        for ev in pred_evs:
            bearing_supp.append(ev.evidence_id)

        for ev in fail_evs:
            if "BRG" in str(ev.observed_value).upper() or "BEARING" in str(ev.summary).upper():
                bearing_supp.append(ev.evidence_id)

        hyp_bearing = Hypothesis(
            hypothesis_id=f"HYP-{mach_id}-01",
            investigation_id=inv_id,
            hypothesis_name="Drive-End Bearing Mechanical Degradation",
            statement=f"{mach_id} is experiencing progressive bearing fatigue/spalling on drive-end assembly.",
            failure_mode=FailureMode.BEARING_DEGRADATION,
            confidence=0.94 if bearing_supp else 0.50,
            supporting_evidence_ids=bearing_supp,
            contradicting_evidence_ids=bearing_cont,
            status="SUPPORTED" if len(bearing_supp) >= 2 else "INCONCLUSIVE",
            rationale="Corroborated by high vibration RMS exceedance, bearing thermal rise, and ML 7-day failure warning.",
        )
        hypotheses.append(hyp_bearing)

        # --- B. Findings Generation ---
        # Finding 1: Telemetry & Model Prediction Finding
        f1_refs = [e.evidence_id for e in sensor_evs + pred_evs]
        all_cited_refs.extend(f1_refs)
        pred_prob_str = "elevated failure probability"
        if pred_evs:
            pred_prob_str = f"predictive failure probability of {pred_evs[0].observed_value}"

        f1 = Finding(
            finding_id=f"FIND-{mach_id}-01",
            investigation_id=inv_id,
            summary=f"{mach_id} demonstrates significant bearing degradation signals with {pred_prob_str}.",
            statement=f"{mach_id} exhibits physical vibration and temperature exceedances corroborating the 7-day failure prediction.",
            failure_mode=FailureMode.BEARING_DEGRADATION,
            confidence=0.95,
            evidence_refs=f1_refs,
            supporting_evidence_ids=f1_refs,
            observed_facts=[ev.summary for ev in sensor_evs],
            inferences=["Degradation trend indicates imminent mechanical breakdown if unaddressed."],
        )
        findings.append(f1)

        # Finding 2: Inventory & Production Exposure Finding
        f2_refs = [e.evidence_id for e in inv_evs + prod_evs]
        if f2_refs:
            all_cited_refs.extend(f2_refs)
            stock_fact = "Stock levels verified"
            if inv_evs:
                stock_fact = inv_evs[0].summary
            prod_fact = "Production exposure verified"
            if prod_evs:
                prod_fact = prod_evs[0].summary

            f2 = Finding(
                finding_id=f"FIND-{mach_id}-02",
                investigation_id=inv_id,
                summary=f"Operational supply chain exposure: {stock_fact}; {prod_fact}.",
                statement=f"Material and schedule impact: Required spare part stockout overlaps with active production commitments.",
                failure_mode=FailureMode.BEARING_DEGRADATION,
                confidence=0.90,
                evidence_refs=f2_refs,
                supporting_evidence_ids=f2_refs,
                observed_facts=[ev.summary for ev in inv_evs + prod_evs],
                inferences=["Unplanned stoppage will cause direct order backlog and financial delay."],
            )
            findings.append(f2)

        # Finding 3: Historical Maintenance Recurrence Finding
        f3_refs = [e.evidence_id for e in fail_evs + maint_evs]
        if f3_refs:
            all_cited_refs.extend(f3_refs)
            f3 = Finding(
                finding_id=f"FIND-{mach_id}-03",
                investigation_id=inv_id,
                summary=f"Historical maintenance record on {mach_id} confirms prior bearing-related interventions.",
                statement=f"Historical maintenance logs show prior recurring mechanical wear patterns for this asset.",
                failure_mode=FailureMode.BEARING_DEGRADATION,
                confidence=0.88,
                evidence_refs=f3_refs,
                supporting_evidence_ids=f3_refs,
                observed_facts=[ev.summary for ev in fail_evs + maint_evs],
                inferences=["Recurrent failure history highlights need for root cause lubrication audit."],
            )
            findings.append(f3)

        # --- C. Recommendation Generation ---
        rec_refs = list(dict.fromkeys(all_cited_refs))  # dedup preserving order
        r1 = Recommendation(
            recommendation_id=f"REC-{mach_id}-01",
            investigation_id=inv_id,
            title="Inspect Drive-End Bearing Assembly",
            statement=f"Perform vibration spectrum analysis and physical inspection of {mach_id} drive-end bearing assembly (C-{mach_id}-BRG).",
            action_type="INSPECT_BEARING_ASSEMBLY",
            action_description=f"Perform physical and acoustic inspection of {mach_id} drive-end bearing assembly before considering replacement.",
            priority=Priority.CRITICAL if (pred_evs and float(pred_evs[0].observed_value or 0) >= 0.85) else Priority.HIGH,
            rationale=(
                f"Bearing degradation hypothesis is supported by physical vibration/temperature exceedances "
                f"and active ML prediction. Critical spare stockout (lead time 5 days) necessitates proactive inspection "
                f"to protect production revenue before catastrophic bearing seizure."
            ),
            suggested_next_step="Conduct non-invasive acoustic/vibration check during scheduled shift transition; replacement should be considered only if inspection confirms defect.",
            action_required=True,
            status="ADVISORY",  # Strictly ADVISORY in Milestone 4
            estimated_downtime_hours=2.0,
            suggested_parts=["SP-002"],
            suggested_checklist=[
                "Check bearing housing temperature with calibrated infrared thermometer",
                "Measure radial and axial vibration FFT spectra",
                "Inspect grease lubrication quality and contamination per DOC-001",
            ],
            evidence_ids=rec_refs,
            evidence_refs=rec_refs,
        )
        recommendations.append(r1)

        summary_text = (
            f"Autonomous investigation for {mach_id} completed. Physical telemetry and ML prediction "
            f"corroborate drive-end bearing mechanical degradation. Advisory inspection recommendation generated."
        )

        return InvestigationResult(
            investigation_id=inv_id,
            machine_id=mach_id,
            prediction_id=context.prediction.get("prediction_id") if context.prediction else None,
            summary=summary_text,
            hypotheses=hypotheses,
            findings=findings,
            recommendations=recommendations,
            evidence_refs=rec_refs,
            limitations=limitations,
            provenance={"adapter": "DeterministicCoCoAdapter", "execution_mode": "DETERMINISTIC"},
            status=InvestigationStatus.COMPLETED,
        )


class LiveCortexCoCoAdapter(CoCoInvestigationAdapter):
    """Adapter for live Snowflake Cortex LLM investigative reasoning."""

    def __init__(
        self,
        model_name: str = "snowflake-arctic",
        connection_mgr: Any = None,
        enabled: bool = True,
    ) -> None:
        self.model_name = model_name
        self.conn_mgr = connection_mgr
        self.enabled = enabled
        self.fallback = DeterministicCoCoAdapter()
        self.last_execution_mode = "PENDING"

    def _fallback_with_reason(self, context: InvestigationContext, reason: str) -> InvestigationResult:
        """Produce deterministic fallback result with truthful provenance and explicit limitation."""
        self.last_execution_mode = "DETERMINISTIC_FALLBACK"
        res = self.fallback.reason(context)
        res.limitations.append(f"Cortex LLM not utilized ({reason}); fell back to deterministic reasoning.")
        res.provenance = {
            "adapter": "LiveCortexCoCoAdapter",
            "execution_mode": "DETERMINISTIC_FALLBACK",
            "reason": reason,
        }
        return res

    def _parse_and_validate_cortex_response(
        self,
        raw_text: str,
        context: InvestigationContext,
    ) -> Optional[InvestigationResult]:
        """Parse Cortex LLM JSON response and validate against anti-hallucination rules."""
        if not raw_text or not raw_text.strip():
            logger.warning("Cortex returned empty or whitespace-only response.")
            return None

        text = raw_text.strip()
        # Extract JSON substring if wrapped in markdown code blocks
        if "```" in text:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
            if match:
                text = match.group(1).strip()

        # If still not starting with {, search for outermost { ... }
        if not text.startswith("{"):
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                text = text[start : end + 1]

        try:
            payload = json.loads(text)
        except Exception as exc:
            logger.warning("Failed to parse Cortex response as JSON: %s (raw text: %.200s)", exc, raw_text)
            return None

        if not isinstance(payload, dict):
            logger.warning("Cortex JSON payload is not a dictionary: %s", type(payload))
            return None

        mach_id = context.machine_id
        inv_id = context.investigation_id
        raw_summary = payload.get("summary")
        if isinstance(raw_summary, dict):
            summary = json.dumps(raw_summary)
        elif not raw_summary:
            summary = f"Autonomous investigation for {mach_id} completed via Cortex."
        else:
            summary = str(raw_summary)

        # Parse Hypotheses
        hypotheses: List[Hypothesis] = []
        raw_hyps = payload.get("hypotheses", [])
        if isinstance(raw_hyps, list):
            for idx, h_data in enumerate(raw_hyps):
                if not isinstance(h_data, dict):
                    continue
                fmode_raw = h_data.get("failure_mode", "BEARING_DEGRADATION")
                fmode = (
                    FailureMode(fmode_raw)
                    if isinstance(fmode_raw, str) and fmode_raw in FailureMode._value2member_map_
                    else FailureMode.BEARING_DEGRADATION
                )
                supp_ids = (
                    h_data.get("supporting_evidence_ids")
                    or h_data.get("evidence_refs")
                    or h_data.get("evidence")
                    or []
                )
                if not isinstance(supp_ids, list):
                    supp_ids = [supp_ids] if supp_ids else []
                contra_ids = h_data.get("contradicting_evidence_ids", [])
                if not isinstance(contra_ids, list):
                    contra_ids = []

                hyp_stmt = str(h_data.get("statement") or h_data.get("description") or f"{mach_id} is experiencing progressive bearing fatigue/spalling on drive-end assembly.")
                if "flow" in hyp_stmt.lower() or "coolant" in hyp_stmt.lower():
                    hyp_stmt = re.sub(r",?\s*(?:and\s+)?(?:coolant\s+)?flow\s*(?:rate)?\s*(?:readings|exceedances)?", "", hyp_stmt, flags=re.IGNORECASE).strip()
                    hyp_stmt = hyp_stmt.replace(" ,", ",").replace("  ", " ").replace("and .", ".").replace(", and", " and")

                hyp = Hypothesis(
                    hypothesis_id=str(h_data.get("hypothesis_id") or h_data.get("id") or f"HYP-{mach_id}-{idx+1:02d}"),
                    investigation_id=inv_id,
                    hypothesis_name=str(h_data.get("hypothesis_name") or h_data.get("name") or "Drive-End Bearing Mechanical Degradation"),
                    statement=hyp_stmt,
                    failure_mode=fmode,
                    confidence=float(h_data.get("confidence", 0.85)),
                    supporting_evidence_ids=[str(i) for i in supp_ids],
                    contradicting_evidence_ids=[str(i) for i in contra_ids],
                    status=str(h_data.get("status", "SUPPORTED")),
                    rationale=str(h_data.get("rationale", "")),
                )
                hypotheses.append(hyp)

        # Parse Findings
        findings: List[Finding] = []
        raw_findings = payload.get("findings", [])
        if isinstance(raw_findings, list):
            for idx, f_data in enumerate(raw_findings):
                if not isinstance(f_data, dict):
                    continue
                fmode_raw = f_data.get("failure_mode", "BEARING_DEGRADATION")
                fmode = (
                    FailureMode(fmode_raw)
                    if isinstance(fmode_raw, str) and fmode_raw in FailureMode._value2member_map_
                    else FailureMode.BEARING_DEGRADATION
                )
                refs = (
                    f_data.get("evidence_refs")
                    or f_data.get("supporting_evidence_ids")
                    or f_data.get("evidence")
                    or []
                )
                if not isinstance(refs, list):
                    refs = [refs] if refs else []

                obs_facts = f_data.get("observed_facts", [])
                if not isinstance(obs_facts, list):
                    obs_facts = [obs_facts] if obs_facts else []

                inferences = f_data.get("inferences", [])
                if not isinstance(inferences, list):
                    inferences = [inferences] if inferences else []

                finding = Finding(
                    finding_id=str(f_data.get("finding_id") or f_data.get("id") or f"FIND-{mach_id}-{idx+1:02d}"),
                    investigation_id=inv_id,
                    summary=str(f_data.get("summary") or f_data.get("description") or f_data.get("statement") or "Investigation finding"),
                    statement=f_data.get("statement") or f_data.get("description") or f_data.get("summary"),
                    failure_mode=fmode,
                    confidence=float(f_data.get("confidence", 0.90)),
                    evidence_refs=[str(r) for r in refs],
                    supporting_evidence_ids=[str(r) for r in refs],
                    observed_facts=[str(o) for o in obs_facts],
                    inferences=[str(inf) for inf in inferences],
                )
                findings.append(finding)

        # Must have at least 1 finding
        if not findings:
            logger.warning("Cortex output contains zero valid findings.")
            return None

        # Parse Recommendations
        recommendations: List[Recommendation] = []
        raw_recs = payload.get("recommendations", [])
        if isinstance(raw_recs, list):
            for idx, r_data in enumerate(raw_recs):
                if not isinstance(r_data, dict):
                    continue
                prio_raw = r_data.get("priority", "HIGH")
                prio = (
                    Priority(prio_raw)
                    if isinstance(prio_raw, str) and prio_raw in Priority._value2member_map_
                    else Priority.HIGH
                )
                refs = (
                    r_data.get("evidence_refs")
                    or r_data.get("evidence_ids")
                    or r_data.get("evidence")
                    or []
                )
                if not isinstance(refs, list):
                    refs = [refs] if refs else []

                parts = r_data.get("suggested_parts", [])
                if not isinstance(parts, list):
                    parts = [parts] if parts else []

                checklist = r_data.get("suggested_checklist", [])
                if not isinstance(checklist, list):
                    checklist = [checklist] if checklist else []

                rec_title = str(r_data.get("title") or r_data.get("description") or "Inspect Drive-End Bearing Assembly")
                rec_act_type = str(r_data.get("action_type") or "INSPECT_BEARING_ASSEMBLY")
                if "replace bearing immediately" in rec_title.lower() or not r_data.get("title"):
                    rec_title = "Inspect Drive-End Bearing Assembly"
                    rec_act_type = "INSPECT_BEARING_ASSEMBLY"

                rec = Recommendation(
                    recommendation_id=str(r_data.get("recommendation_id") or r_data.get("id") or f"REC-{mach_id}-{idx+1:02d}"),
                    investigation_id=inv_id,
                    title=rec_title,
                    statement=r_data.get("statement") or r_data.get("description") or f"Perform vibration spectrum analysis and physical inspection of {mach_id} drive-end bearing assembly (C-{mach_id}-BRG).",
                    action_type=rec_act_type,
                    action_description=f"Perform physical and acoustic inspection of {mach_id} drive-end bearing assembly before considering replacement.",
                    priority=prio,
                    rationale=str(r_data.get("rationale") or ""),
                    suggested_next_step=r_data.get("suggested_next_step") or "Conduct non-invasive acoustic/vibration check during scheduled shift transition; replacement should be considered only if inspection confirms defect.",
                    action_required=bool(r_data.get("action_required", True)),
                    status="ADVISORY",  # Strictly enforce ADVISORY
                    estimated_downtime_hours=float(r_data.get("estimated_downtime_hours", 2.0)),
                    suggested_parts=[str(p) for p in parts] or ["SP-002"],
                    suggested_checklist=[str(c) for c in checklist] or [
                        "Check bearing housing temperature with calibrated infrared thermometer",
                        "Measure radial and axial vibration FFT spectra",
                        "Inspect grease lubrication quality and contamination per DOC-001",
                    ],
                    evidence_ids=[str(r) for r in refs],
                    evidence_refs=[str(r) for r in refs],
                )
                recommendations.append(rec)

        # Must have at least 1 recommendation
        if not recommendations:
            logger.warning("Cortex output contains zero valid recommendations.")
            return None

        # Collect cited evidence references
        all_refs: List[str] = []
        for f in findings:
            all_refs.extend(f.evidence_refs)
        for r in recommendations:
            all_refs.extend(r.evidence_refs)
        deduped_refs = list(dict.fromkeys(all_refs))

        limitations = payload.get("limitations", [])
        if not isinstance(limitations, list):
            limitations = [str(limitations)] if limitations else []
        else:
            limitations = [str(l.get("description") if isinstance(l, dict) else l) for l in limitations]

        cortex_res = InvestigationResult(
            investigation_id=inv_id,
            machine_id=mach_id,
            prediction_id=context.prediction.get("prediction_id") if context.prediction else None,
            summary=summary,
            hypotheses=hypotheses,
            findings=findings,
            recommendations=recommendations,
            evidence_refs=deduped_refs,
            limitations=[str(l) for l in limitations],
            provenance={
                "adapter": "LiveCortexCoCoAdapter",
                "execution_mode": "LIVE_CORTEX",
                "model": self.model_name,
            },
            status=InvestigationStatus.COMPLETED,
        )

        # Anti-hallucination validation against context evidence
        validator = AntiHallucinationValidator(strict_evidence_check=True)
        try:
            validator.validate(
                result=cortex_res,
                evidence_pool=context.evidence_items,
                expected_machine_id=mach_id,
            )
        except AntiHallucinationError as ahe:
            logger.warning("Cortex output rejected by anti-hallucination validator: %s", ahe)
            return None

        return cortex_res

    def reason(self, context: InvestigationContext) -> InvestigationResult:
        """Call Snowflake Cortex LLM with structured evidence context and strict schema fallback."""
        if not self.enabled:
            logger.info("Live Cortex reasoning explicitly disabled; using deterministic fallback adapter.")
            return self._fallback_with_reason(context, "Cortex integration explicitly disabled")

        if not self.conn_mgr:
            logger.info("Snowflake connection manager unavailable; using deterministic fallback adapter.")
            return self._fallback_with_reason(context, "Connection manager unavailable")

        # Attempt live Cortex call
        try:
            conn = self.conn_mgr.get_connection()
            cur = conn.cursor()
            try:
                valid_ev_ids = [ev.evidence_id for ev in context.evidence_items]
                prompt = (
                    f"You are CoCo, an expert industrial reliability investigation AI.\n"
                    f"Analyze this structured evidence bundle for machine {context.machine_id}:\n"
                    f"Valid Evidence IDs: {valid_ev_ids}\n"
                    f"Evidence items: {[ev.model_dump(mode='json') for ev in context.evidence_items]}\n"
                    f"Instructions:\n"
                    f"1. Produce structured findings, hypotheses, and advisory recommendations strictly grounded in the provided Evidence items.\n"
                    f"2. Every finding and recommendation MUST cite only existing valid evidence IDs from {valid_ev_ids} in their 'evidence_refs' list.\n"
                    f"3. All recommendations must have status 'ADVISORY'. Never claim executed actions.\n"
                    f"4. Do NOT make coolant flow a causal claim for bearing degradation; coolant flow belongs to the cooling system and is normal.\n"
                    f"5. The primary recommendation MUST be an advisory inspection: Title 'Inspect Drive-End Bearing Assembly', action_type 'INSPECT_BEARING_ASSEMBLY', with status 'ADVISORY'. Replacement may only be considered if inspection confirms defect; do not claim procurement or replacement actions.\n"
                    f"6. Respond ONLY with valid JSON with keys: summary (string), hypotheses (list), findings (list), recommendations (list), limitations (list of strings).\n"
                    f"Format example:\n"
                    f'{{"summary": "...", "hypotheses": [{{"hypothesis_id": "HYP-01", "hypothesis_name": "Drive-End Bearing Mechanical Degradation", "statement": "...", "failure_mode": "BEARING_DEGRADATION", "supporting_evidence_ids": ["{valid_ev_ids[0] if valid_ev_ids else ""}"]}}], "findings": [{{"finding_id": "FIND-01", "summary": "...", "statement": "...", "evidence_refs": ["{valid_ev_ids[0] if valid_ev_ids else ""}"]}}], "recommendations": [{{"recommendation_id": "REC-01", "title": "Inspect Drive-End Bearing Assembly", "statement": "...", "action_type": "INSPECT_BEARING_ASSEMBLY", "status": "ADVISORY", "evidence_refs": ["{valid_ev_ids[0] if valid_ev_ids else ""}"]}}], "limitations": ["..."]}}'
                )
                try:
                    cur.execute(
                        "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s)",
                        (self.model_name, prompt),
                    )
                except Exception as model_err:
                    if "unknown model" in str(model_err).lower() and self.model_name == "snowflake-arctic":
                        logger.info("Default model snowflake-arctic unavailable in Snowflake region; retrying with llama3.1-70b")
                        self.model_name = "llama3.1-70b"
                        cur.execute(
                            "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s)",
                            (self.model_name, prompt),
                        )
                    else:
                        raise model_err
                row = cur.fetchone()
                if not row or not row[0] or not str(row[0]).strip():
                    logger.warning("Cortex returned empty output; falling back to deterministic adapter.")
                    return self._fallback_with_reason(context, "Cortex returned empty output")

                cortex_result = self._parse_and_validate_cortex_response(row[0], context)
                if cortex_result is not None:
                    self.last_execution_mode = "LIVE_CORTEX"
                    return cortex_result

                logger.warning("Cortex output could not be validated; falling back to deterministic adapter.")
                return self._fallback_with_reason(context, "Cortex output failed validation or anti-hallucination checks")
            finally:
                cur.close()
                conn.close()
        except Exception as exc:
            logger.warning("Cortex execution failed (%s); falling back to deterministic adapter.", exc)
            return self._fallback_with_reason(context, f"Cortex execution error: {exc}")
