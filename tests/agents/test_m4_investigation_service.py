"""Test suite for Milestone 4 InvestigationService lifecycle, idempotency, and trigger resolution."""

import pytest
from domain.enums import TriggerType, InvestigationStatus
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
def service(repo):
    tools = create_m4_tool_registry(repo)
    reasoner = DeterministicCoCoAdapter()
    validator = AntiHallucinationValidator()
    return InvestigationService(
        repository=repo,
        tool_registry=tools,
        reasoner=reasoner,
        validator=validator,
    )


def test_investigation_service_lifecycle_from_machine_trigger(service, repo):
    """Verify complete end-to-end lifecycle when triggered by MACHINE."""
    req = InvestigationRequest(
        request_id="REQ-001",
        investigation_id="INV-TEST-M21-01",
        trigger_type=TriggerType.MACHINE,
        machine_id="M21",
    )

    result = service.investigate(req)

    assert result is not None
    assert result.investigation_id == "INV-TEST-M21-01"
    assert result.machine_id == "M21"
    assert result.status == InvestigationStatus.COMPLETED
    assert len(result.findings) >= 1
    assert len(result.recommendations) >= 1
    assert result.recommendations[0].status == "ADVISORY"

    # Verify persistence in repository
    persisted = repo.get_investigation("INV-TEST-M21-01")
    assert persisted is not None
    assert persisted.status == InvestigationStatus.COMPLETED
    assert len(persisted.evidence) > 0


def test_investigation_service_idempotency(service, repo):
    """Calling investigate() twice with the same investigation_id must return the existing record without side effects."""
    req = InvestigationRequest(
        request_id="REQ-002",
        investigation_id="INV-IDEMP-01",
        trigger_type=TriggerType.MACHINE,
        machine_id="M21",
    )

    res1 = service.investigate(req)
    evidence_count_1 = len(repo.get_evidence("INV-IDEMP-01"))

    # Second call
    res2 = service.investigate(req)
    evidence_count_2 = len(repo.get_evidence("INV-IDEMP-01"))

    assert res1.investigation_id == res2.investigation_id
    assert res1.summary == res2.summary
    assert evidence_count_1 == evidence_count_2


def test_trigger_resolution_from_user_query(service):
    """Verify that user queries like 'Investigate Grinder 3 vibration' correctly resolve to M21."""
    req = InvestigationRequest(
        request_id="REQ-003",
        investigation_id="INV-UQ-01",
        trigger_type=TriggerType.USER_QUERY,
        machine_id="",  # empty machine_id
        user_query="Please investigate Grinder 3 bearing vibration anomalies",
    )

    machine_id, comp_id, pred = service.resolve_trigger(req)
    assert machine_id == "M21"
    assert comp_id == "C-M21-BRG"


def test_trigger_resolution_from_prediction(service, repo):
    """Verify trigger resolution from canonical prediction ID PRED-000322."""
    req = InvestigationRequest(
        request_id="REQ-004",
        investigation_id="INV-PRED-01",
        trigger_type=TriggerType.PREDICTION,
        machine_id="",
        prediction_id="PRED-000322",
    )

    machine_id, comp_id, pred = service.resolve_trigger(req)
    assert machine_id == "M21"
    assert comp_id == "C-M21-BRG"
    assert pred is not None
    assert pred.prediction_id == "PRED-000322"
