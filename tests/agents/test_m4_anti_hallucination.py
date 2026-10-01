"""Test suite for Milestone 4 Anti-Hallucination and Evidence Grounding Validator.

Verifies:
- Enforcement of evidence references for all findings and recommendations
- Immediate rejection of fabricated evidence IDs
- Immediate rejection of non-ADVISORY recommendation statuses
- Immediate rejection of executed action claims
- Immediate rejection of hallucinated machine or component IDs
"""

import pytest
from domain.enums import FailureMode, Priority, InvestigationStatus
from domain.models import (
    Evidence,
    Finding,
    Recommendation,
    InvestigationResult,
)
from agents.reliability.anti_hallucination import (
    AntiHallucinationValidator,
    AntiHallucinationError,
)


@pytest.fixture
def validator():
    return AntiHallucinationValidator(strict_evidence_check=True)


@pytest.fixture
def sample_evidence():
    return [
        Evidence(
            evidence_id="EV-PRED-001",
            investigation_id="INV-001",
            evidence_type="PREDICTION",
            category="PREDICTION",
            metric="failure_probability",
            observed_value=0.95,
            claim="Prediction failure probability is 0.95",
            summary="High predictive risk",
        ),
        Evidence(
            evidence_id="EV-VIB-001",
            investigation_id="INV-001",
            evidence_type="TELEMETRY",
            category="SENSOR",
            metric="vibration_rms",
            observed_value=4.88,
            unit="mm/s",
            severity="CRITICAL",
            claim="Vibration RMS exceeded threshold",
            summary="Sensor vibration critical",
        ),
    ]


def test_validator_accepts_grounded_result(validator, sample_evidence):
    """Validation must succeed when findings and recommendations strictly reference collected evidence."""
    result = InvestigationResult(
        investigation_id="INV-001",
        machine_id="M21",
        summary="Investigation summary grounded in evidence",
        findings=[
            Finding(
                finding_id="F-001",
                investigation_id="INV-001",
                summary="Vibration signals indicate degradation",
                failure_mode=FailureMode.BEARING_DEGRADATION,
                evidence_refs=["EV-PRED-001", "EV-VIB-001"],
            )
        ],
        recommendations=[
            Recommendation(
                recommendation_id="REC-001",
                investigation_id="INV-001",
                title="Inspect Bearing Assembly",
                statement="Advise physical inspection of drive-end bearing assembly",
                action_type="INSPECT_BEARING",
                status="ADVISORY",
                priority=Priority.CRITICAL,
                evidence_refs=["EV-VIB-001"],
            )
        ],
        status=InvestigationStatus.COMPLETED,
    )

    validator.validate(
        result=result,
        evidence_pool=sample_evidence,
        expected_machine_id="M21",
        valid_component_ids={"C-M21-BRG", "C-M21-MTR"},
    )


def test_validator_rejects_hallucinated_evidence_id(validator, sample_evidence):
    """Validation must fail if a finding cites an evidence ID not present in collected evidence."""
    result = InvestigationResult(
        investigation_id="INV-001",
        machine_id="M21",
        summary="Invalid reference result",
        findings=[
            Finding(
                finding_id="F-001",
                investigation_id="INV-001",
                summary="Vibration anomaly",
                evidence_refs=["EV-FABRICATED-999"],
            )
        ],
        recommendations=[
            Recommendation(
                recommendation_id="REC-001",
                investigation_id="INV-001",
                title="Inspect",
                evidence_refs=["EV-VIB-001"],
            )
        ],
    )

    with pytest.raises(AntiHallucinationError, match="references non-existent evidence ID"):
        validator.validate(result=result, evidence_pool=sample_evidence, expected_machine_id="M21")


def test_validator_rejects_non_advisory_status(validator, sample_evidence):
    """Validation must fail if a recommendation has non-advisory status."""
    result = InvestigationResult(
        investigation_id="INV-001",
        machine_id="M21",
        summary="Non-advisory recommendation",
        findings=[
            Finding(
                finding_id="F-001",
                investigation_id="INV-001",
                summary="Vibration anomaly",
                evidence_refs=["EV-PRED-001"],
            )
        ],
        recommendations=[
            Recommendation(
                recommendation_id="REC-001",
                investigation_id="INV-001",
                title="Inspect",
                status="EXECUTED",  # FORBIDDEN in M4
                evidence_refs=["EV-VIB-001"],
            )
        ],
    )

    with pytest.raises(AntiHallucinationError, match="non-advisory status"):
        validator.validate(result=result, evidence_pool=sample_evidence, expected_machine_id="M21")


def test_validator_rejects_action_claims(validator, sample_evidence):
    """Validation must fail if recommendation text claims an action was executed or scheduled."""
    result = InvestigationResult(
        investigation_id="INV-001",
        machine_id="M21",
        summary="Action claim recommendation",
        findings=[
            Finding(
                finding_id="F-001",
                investigation_id="INV-001",
                summary="Vibration anomaly",
                evidence_refs=["EV-PRED-001"],
            )
        ],
        recommendations=[
            Recommendation(
                recommendation_id="REC-001",
                investigation_id="INV-001",
                title="Work order created for bearing replacement",  # Prohibited phrase
                status="ADVISORY",
                evidence_refs=["EV-VIB-001"],
            )
        ],
    )

    with pytest.raises(AntiHallucinationError, match="claims executed action"):
        validator.validate(result=result, evidence_pool=sample_evidence, expected_machine_id="M21")


def test_validator_rejects_hallucinated_component(validator, sample_evidence):
    """Validation must fail if finding text mentions a component ID not in topology."""
    result = InvestigationResult(
        investigation_id="INV-001",
        machine_id="M21",
        summary="Component hallucination",
        findings=[
            Finding(
                finding_id="F-001",
                investigation_id="INV-001",
                statement="Severe failure detected on M21-IMAGINARY-PART",
                evidence_refs=["EV-PRED-001"],
            )
        ],
        recommendations=[
            Recommendation(
                recommendation_id="REC-001",
                investigation_id="INV-001",
                title="Inspect",
                status="ADVISORY",
                evidence_refs=["EV-VIB-001"],
            )
        ],
    )

    with pytest.raises(AntiHallucinationError, match="mentions hallucinated component ID"):
        validator.validate(
            result=result,
            evidence_pool=sample_evidence,
            expected_machine_id="M21",
            valid_component_ids={"C-M21-BRG"},
        )
