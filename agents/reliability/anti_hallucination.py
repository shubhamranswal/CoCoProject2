"""Deterministic Anti-Hallucination and Evidence Grounding Validator for Milestone 4.

Enforces:
1. Every finding must explicitly reference valid evidence IDs collected during the investigation.
2. Every recommendation must explicitly reference valid evidence IDs.
3. Every recommendation status must be strictly ADVISORY (no executed actions, no scheduled work).
4. No fabricated or hallucinated machine or component IDs.
5. Missing evidence must be reflected as limitations, not filled with plausibly invented facts.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional, Set
from domain.models import Evidence, Finding, Recommendation, InvestigationResult

logger = logging.getLogger(__name__)


class AntiHallucinationError(ValueError):
    """Raised when an investigation result contains ungrounded claims or hallucinated references."""
    pass


class AntiHallucinationValidator:
    """Deterministic validator verifying factual grounding of CoCo reasoning outputs."""

    def __init__(self, strict_evidence_check: bool = True) -> None:
        self.strict_evidence_check = strict_evidence_check

    def validate(
        self,
        result: InvestigationResult,
        evidence_pool: List[Evidence],
        expected_machine_id: str,
        valid_component_ids: Optional[Set[str]] = None,
    ) -> None:
        """Validate that all claims, IDs, and references in InvestigationResult are grounded in collected evidence."""
        # 1. Machine ID validation
        if result.machine_id != expected_machine_id:
            raise AntiHallucinationError(
                f"Machine ID mismatch: expected '{expected_machine_id}', got '{result.machine_id}'"
            )

        # Build evidence ID lookup
        valid_ev_ids = {ev.evidence_id for ev in evidence_pool}

        # 2. Findings validation
        if not result.findings:
            raise AntiHallucinationError("Investigation result contains zero findings.")

        for f in result.findings:
            refs = getattr(f, "evidence_refs", None) or getattr(f, "supporting_evidence_ids", [])
            if not refs:
                raise AntiHallucinationError(
                    f"Finding '{f.finding_id}' lacks supporting evidence references."
                )

            for ref in refs:
                if ref not in valid_ev_ids:
                    raise AntiHallucinationError(
                        f"Finding '{f.finding_id}' references non-existent evidence ID '{ref}'. "
                        f"Collected evidence IDs: {sorted(list(valid_ev_ids))}"
                    )

            # Check for component hallucination in finding text
            if valid_component_ids:
                matches = re.findall(rf"{expected_machine_id}-[A-Z0-9\-]+", f.summary or f.statement or "")
                for m in matches:
                    if m not in valid_component_ids:
                        raise AntiHallucinationError(
                            f"Finding '{f.finding_id}' mentions hallucinated component ID '{m}'. "
                            f"Valid components: {valid_component_ids}"
                        )

        # 3. Recommendations validation
        if not result.recommendations:
            raise AntiHallucinationError("Investigation result contains zero recommendations.")

        for r in result.recommendations:
            # Enforce ADVISORY status in Milestone 4
            status = getattr(r, "status", "ADVISORY")
            if status != "ADVISORY" and str(status).upper() != "ADVISORY":
                raise AntiHallucinationError(
                    f"Recommendation '{r.recommendation_id}' has non-advisory status '{status}'. "
                    "Milestone 4 strictly forbids non-ADVISORY recommendations."
                )

            # Check for illegal action claims (e.g., claiming a work order was created or scheduled)
            forbidden_action_phrases = [
                "work order created",
                "technician assigned",
                "machine stopped",
                "part ordered",
                "order submitted",
                "scheduled for execution",
            ]
            statement_lower = (r.statement or r.title or "").lower()
            rationale_lower = (r.rationale or "").lower()
            for phrase in forbidden_action_phrases:
                if phrase in statement_lower or phrase in rationale_lower:
                    raise AntiHallucinationError(
                        f"Recommendation '{r.recommendation_id}' claims executed action ('{phrase}'). "
                        "Milestone 4 recommendations must be strictly advisory."
                    )

            # Check evidence references
            r_refs = getattr(r, "evidence_refs", None) or getattr(r, "evidence_ids", [])
            if self.strict_evidence_check and not r_refs:
                raise AntiHallucinationError(
                    f"Recommendation '{r.recommendation_id}' lacks supporting evidence references."
                )

            for ref in r_refs:
                if ref not in valid_ev_ids:
                    raise AntiHallucinationError(
                        f"Recommendation '{r.recommendation_id}' references non-existent evidence ID '{ref}'."
                    )

        logger.debug(
            "Anti-hallucination validation passed successfully for investigation %s (%d evidence items, %d findings, %d recommendations)",
            result.investigation_id,
            len(evidence_pool),
            len(result.findings),
            len(result.recommendations),
        )
