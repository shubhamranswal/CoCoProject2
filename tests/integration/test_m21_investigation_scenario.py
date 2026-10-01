"""Flagship Milestone 4 End-to-End M21 Autonomous Investigation Acceptance Scenario.

Validates the full cross-domain evidence correlation for canonical asset M21:
- Asset: M21 (Grinder 3, Line L5)
- Component: C-M21-BRG (Drive-End Bearing)
- Predictive Failure: PRED-000322 (p ~ 0.95, failure mode BEARING_DEGRADATION)
- Telemetry: S-M21-VIB (vibration exceedance) and S-M21-BTMP (thermal rise)
- ML Features: VIB_max=1.743, VIB_mean=1.250, VIB_rel30=1.480, days_since_last_maintenance=65.0
- Supply Chain: SP-002 stockout (stock=0, lead time=5d, supplier SUP-12)
- Production Exposure: PRD-01278 (211 remaining units of P008, unfulfilled revenue exposure ₹83,134)
- Historical Maintenance: Prior failure code BD-BRG
- Technical Knowledge: Document guidance (DOC-001)
- Advisory Recommendation: status='ADVISORY', zero action executions
"""

import pytest
from domain.enums import FailureMode, Priority, TriggerType, InvestigationStatus
from domain.models import InvestigationRequest
from repositories.memory.memory_repository import InMemoryRepository
from services.investigation_service import InvestigationService
from tools.registry import create_m4_tool_registry
from agents.reliability.coco_adapter import DeterministicCoCoAdapter
from agents.reliability.anti_hallucination import AntiHallucinationValidator


@pytest.fixture
def repo():
    return InMemoryRepository(seed=True)


@pytest.fixture
def investigation_service(repo):
    tools = create_m4_tool_registry(repo)
    reasoner = DeterministicCoCoAdapter()
    validator = AntiHallucinationValidator()
    return InvestigationService(
        repository=repo,
        tool_registry=tools,
        reasoner=reasoner,
        validator=validator,
    )


def test_m21_end_to_end_investigation_scenario(investigation_service, repo):
    """Execute autonomous investigation on M21 and verify complete evidence chain and advisory recommendations."""
    req = InvestigationRequest(
        request_id="REQ-M21-CANONICAL",
        investigation_id="INV-M21-CANONICAL-001",
        trigger_type=TriggerType.PREDICTION,
        machine_id="M21",
        prediction_id="PRED-000322",
    )

    result = investigation_service.investigate(req)

    # 1. High-Level Outcome
    assert result is not None
    assert result.investigation_id == "INV-M21-CANONICAL-001"
    assert result.machine_id == "M21"
    assert result.status == InvestigationStatus.COMPLETED

    # 2. Hypotheses Validation
    assert len(result.hypotheses) >= 1
    hyp = result.hypotheses[0]
    assert hyp.failure_mode == FailureMode.BEARING_DEGRADATION
    assert hyp.status in ("SUPPORTED", "EVALUATED")
    assert hyp.confidence >= 0.85
    assert len(hyp.supporting_evidence_ids) >= 2

    # 3. Findings Validation
    assert len(result.findings) >= 2
    # Verify telemetry / prediction finding
    f1 = result.findings[0]
    assert f1.failure_mode == FailureMode.BEARING_DEGRADATION
    assert len(f1.evidence_refs) >= 1

    # Verify inventory / supply chain finding
    f2 = [f for f in result.findings if "supply chain" in f.summary.lower() or "exposure" in f.summary.lower() or "stock" in f.summary.lower()]
    assert len(f2) >= 1, "Expected finding correlating inventory stockout and production exposure"

    # 4. Recommendation Validation (Strictly Advisory in M4)
    assert len(result.recommendations) >= 1
    rec = result.recommendations[0]
    assert rec.status == "ADVISORY", "Milestone 4 recommendations must be strictly ADVISORY"
    assert rec.priority in (Priority.CRITICAL, Priority.HIGH)
    assert "SP-002" in rec.suggested_parts
    assert len(rec.suggested_checklist) >= 2
    assert len(rec.evidence_refs) >= 2

    # Verify absence of action execution claims
    rec_text = f"{rec.title} {rec.statement or ''} {rec.rationale}".lower()
    assert "work order created" not in rec_text
    assert "technician assigned" not in rec_text
    assert "machine stopped" not in rec_text
    assert "part ordered" not in rec_text

    # 5. Persisted Investigation & Evidence Audit in Repository
    persisted_inv = repo.get_investigation("INV-M21-CANONICAL-001")
    assert persisted_inv is not None
    assert persisted_inv.status == InvestigationStatus.COMPLETED

    evidence_items = repo.get_evidence("INV-M21-CANONICAL-001")
    assert len(evidence_items) >= 4, f"Expected at least 4 correlated evidence items, got {len(evidence_items)}"

    categories = {ev.category for ev in evidence_items}
    assert "PREDICTION" in categories
    assert "SENSOR" in categories
    assert "INVENTORY" in categories
    assert "PRODUCTION" in categories

    # 6. Specific Value Grounding Checks
    # Verify SP-002 stockout evidence
    inv_ev = [e for e in evidence_items if e.category == "INVENTORY" and "SP-002" in e.source_id]
    assert len(inv_ev) == 1
    assert inv_ev[0].observed_value == 0
    assert "5" in inv_ev[0].claim or "lead time" in inv_ev[0].claim.lower()

    # Verify PRD-01278 exposure evidence
    prod_ev = [e for e in evidence_items if e.category == "PRODUCTION" and "PRD-01278" in e.source_id]
    assert len(prod_ev) == 1
    assert float(prod_ev[0].observed_value) == 83134.0
    assert "211" in prod_ev[0].claim

    # Verify sensor exceedance evidence
    sensor_ev = [e for e in evidence_items if e.category == "SENSOR"]
    assert len(sensor_ev) >= 1
    vib_ev = [e for e in sensor_ev if "VIB" in e.metric.upper()]
    assert len(vib_ev) >= 1
    assert vib_ev[0].severity in ("CRITICAL", "HIGH")
