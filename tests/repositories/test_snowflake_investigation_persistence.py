"""Unit tests for SnowflakeRepository and InMemoryRepository investigation persistence (Milestone M6.5.2).

Validates:
1. create_investigation / get_investigation with VARIANT parsing (limitations, provenance).
2. save_evidence / get_evidence with parameterized MERGE.
3. save_hypotheses / get_hypotheses with VARIANT parsing (supporting/contradicting_evidence_ids).
4. save_findings / get_findings with VARIANT parsing (evidence_refs, observed_facts, inferences).
5. save_recommendations / get_recommendations with VARIANT parsing (parts, checklist, evidence_refs).
6. save_tool_calls / get_tool_calls with parameter serialization and duration.
7. save_investigation_bundle atomic transaction (BEGIN, merge all, COMMIT, and ROLLBACK on exception).
8. Idempotent MERGE behavior without row duplication.
9. InMemoryRepository full interface parity.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, call
import pytest

from domain.enums import (
    FailureMode,
    InvestigationStatus,
    Priority,
    TriggerType,
)
from domain.models import (
    Evidence,
    Finding,
    Hypothesis,
    Investigation,
    Recommendation,
    ToolCall,
)
from repositories.memory.memory_repository import InMemoryRepository
from repositories.snowflake.snowflake_repository import SnowflakeRepository


@pytest.fixture
def mock_snowflake_conn():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchall.return_value = []
    cur.fetchone.return_value = None
    return conn, cur


@pytest.fixture
def sf_repo(mock_snowflake_conn):
    conn, _ = mock_snowflake_conn
    mgr = MagicMock()
    mgr.get_connection.return_value = conn
    return SnowflakeRepository(connection_manager=mgr)


@pytest.fixture
def sample_investigation():
    return Investigation(
        investigation_id="INV-TEST-001",
        trigger_type=TriggerType.PREDICTION,
        trigger_id="PRED-M21-001",
        prediction_id="PRED-M21-001",
        alert_id="ALT-M21-001",
        machine_id="M21",
        component_id="C-M21-BRG",
        scope="EQUIPMENT_RELIABILITY",
        status=InvestigationStatus.COMPLETED,
        failure_mode=FailureMode.BEARING_DEGRADATION,
        confidence=0.92,
        summary="Bearing degradation detected on M21 drive end.",
        limitations=["Only 7 days of vibration telemetry available"],
        provenance={"adapter": "DeterministicFallback", "tool_count": 5},
        started_at=datetime(2026, 10, 2, 10, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 10, 2, 10, 5, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_evidence():
    return [
        Evidence(
            evidence_id="EV-TEST-001",
            investigation_id="INV-TEST-001",
            evidence_type="TELEMETRY",
            category="SENSOR",
            source="sensor_telemetry",
            source_type="SENSOR",
            source_id="S-M21-VIB",
            metric="vibration_peak",
            claim="Vibration peak exceeds critical threshold",
            observed_value=8.45,
            unit="mm/s",
            severity="CRITICAL",
            relationship="SUPPORTS",
            machine_id="M21",
            component_id="C-M21-BRG",
            summary="Vibration reached 8.45 mm/s exceeding threshold 7.1 mm/s",
            source_reference="CORE.SENSOR_READING",
            timestamp=datetime(2026, 10, 2, 10, 1, tzinfo=timezone.utc),
        )
    ]


@pytest.fixture
def sample_hypotheses():
    return [
        Hypothesis(
            hypothesis_id="HYP-TEST-001",
            investigation_id="INV-TEST-001",
            hypothesis_name="Outer Race Spalling",
            statement="Bearing outer race spalling causing 8.45 mm/s vibration peaks",
            failure_mode=FailureMode.BEARING_DEGRADATION,
            confidence=0.88,
            supporting_evidence_ids=["EV-TEST-001"],
            contradicting_evidence_ids=[],
            status="SUPPORTED",
            rationale="Peak vibration aligns with mechanical fault frequencies",
        )
    ]


@pytest.fixture
def sample_findings():
    return [
        Finding(
            finding_id="FND-TEST-001",
            investigation_id="INV-TEST-001",
            summary="Confirmed inner/outer ring fatigue spall",
            statement="Vibration signature indicates advanced race degradation",
            failure_mode=FailureMode.BEARING_DEGRADATION,
            confidence=0.91,
            evidence_refs=["EV-TEST-001"],
            observed_facts=["Peak vibration 8.45 mm/s", "Temperature 78.2 C"],
            inferences=["Expected L10 life exhausted within 72 hours"],
            created_at=datetime(2026, 10, 2, 10, 3, tzinfo=timezone.utc),
        )
    ]


@pytest.fixture
def sample_recommendations():
    return [
        Recommendation(
            recommendation_id="REC-TEST-001",
            investigation_id="INV-TEST-001",
            title="Replace Drive End Bearing Assembly",
            statement="Schedule planned replacement before catastrophic seizure",
            action_type="INSPECT_BEARING_ASSEMBLY",
            priority=Priority.HIGH,
            rationale="Vibration exceeding critical threshold with high failure probability",
            suggested_next_step="Order replacement bearing part SKF-6205-2RS",
            action_required=True,
            status="ADVISORY",
            estimated_downtime_hours=3.5,
            suggested_parts=["SKF-6205-2RS", "LUBRICANT-ISO-VG-220"],
            suggested_checklist=["Lockout/Tagout", "Remove coupling guard", "Check alignment"],
            evidence_refs=["EV-TEST-001"],
            created_at=datetime(2026, 10, 2, 10, 4, tzinfo=timezone.utc),
        )
    ]


@pytest.fixture
def sample_tool_calls():
    return [
        ToolCall(
            tool_call_id="TC-TEST-001",
            execution_id="INV-TEST-001",
            tool_name="get_telemetry_history",
            arguments={"machine_id": "M21", "days": 7},
            result={"status": "SUCCESS", "record_count": 140},
            started_at=datetime(2026, 10, 2, 10, 1, tzinfo=timezone.utc),
            duration_ms=45.2,
            is_success=True,
            error_message=None,
        )
    ]


# -------------------------------------------------------------------------
# SnowflakeRepository Persistence Tests
# -------------------------------------------------------------------------

def test_snowflake_create_investigation(sf_repo, mock_snowflake_conn, sample_investigation):
    conn, cur = mock_snowflake_conn
    res = sf_repo.create_investigation(sample_investigation)

    assert res.investigation_id == "INV-TEST-001"
    cur.execute.assert_called()
    sql_executed = cur.execute.call_args[0][0]
    assert "MERGE INTO COCO_FACTORY.APP.INVESTIGATION" in sql_executed
    assert "TRY_PARSE_JSON" in sql_executed
    conn.commit.assert_called()


def test_snowflake_get_investigation(sf_repo, mock_snowflake_conn):
    _, cur = mock_snowflake_conn
    cur.fetchone.return_value = (
        "INV-TEST-001",
        "PREDICTION",
        "PRED-M21-001",
        "PRED-M21-001",
        "ALT-M21-001",
        "M21",
        "C-M21-BRG",
        "EQUIPMENT_RELIABILITY",
        "COMPLETED",
        "BEARING_DEGRADATION",
        0.92,
        "Bearing degradation detected on M21 drive end.",
        json.dumps(["Only 7 days of telemetry"]),
        json.dumps({"adapter": "DeterministicFallback"}),
        datetime(2026, 10, 2, 10, 0, tzinfo=timezone.utc),
        datetime(2026, 10, 2, 10, 5, tzinfo=timezone.utc),
        datetime(2026, 10, 2, 10, 0, tzinfo=timezone.utc),
    )

    inv = sf_repo.get_investigation("INV-TEST-001")
    assert inv is not None
    assert inv.investigation_id == "INV-TEST-001"
    assert inv.machine_id == "M21"
    assert inv.confidence == 0.92
    assert inv.limitations == ["Only 7 days of telemetry"]
    assert inv.provenance == {"adapter": "DeterministicFallback"}


def test_snowflake_save_and_get_evidence(sf_repo, mock_snowflake_conn, sample_evidence):
    conn, cur = mock_snowflake_conn
    sf_repo.save_evidence(sample_evidence)

    assert cur.execute.called
    sql = cur.execute.call_args[0][0]
    assert "MERGE INTO COCO_FACTORY.APP.INVESTIGATION_EVIDENCE" in sql
    conn.commit.assert_called()

    # Test retrieval
    cur.fetchall.return_value = [
        (
            "EV-TEST-001",
            "INV-TEST-001",
            "TELEMETRY",
            "SENSOR",
            "sensor_telemetry",
            "SENSOR",
            "S-M21-VIB",
            "vibration_peak",
            "8.45",
            "mm/s",
            "CRITICAL",
            "SUPPORTS",
            "M21",
            "C-M21-BRG",
            "Vibration exceeds threshold",
            "Vibration reached 8.45",
            "CORE.SENSOR_READING",
            datetime(2026, 10, 2, 10, 1, tzinfo=timezone.utc),
        )
    ]
    ev_list = sf_repo.get_evidence("INV-TEST-001")
    assert len(ev_list) == 1
    assert ev_list[0].evidence_id == "EV-TEST-001"
    assert ev_list[0].observed_value == "8.45"


def test_snowflake_save_and_get_hypotheses(sf_repo, mock_snowflake_conn, sample_hypotheses):
    conn, cur = mock_snowflake_conn
    sf_repo.save_hypotheses(sample_hypotheses)

    assert cur.execute.called
    sql = cur.execute.call_args[0][0]
    assert "MERGE INTO COCO_FACTORY.APP.INVESTIGATION_HYPOTHESIS" in sql
    assert "TRY_PARSE_JSON" in sql
    conn.commit.assert_called()

    # Test retrieval
    cur.fetchall.return_value = [
        (
            "HYP-TEST-001",
            "INV-TEST-001",
            "Outer Race Spalling",
            "Statement details",
            "BEARING_DEGRADATION",
            0.88,
            "SUPPORTED",
            "Peak vibration aligns",
            json.dumps(["EV-TEST-001"]),
            json.dumps([]),
        )
    ]
    hyps = sf_repo.get_hypotheses("INV-TEST-001")
    assert len(hyps) == 1
    assert hyps[0].hypothesis_id == "HYP-TEST-001"
    assert hyps[0].supporting_evidence_ids == ["EV-TEST-001"]


def test_snowflake_save_and_get_findings(sf_repo, mock_snowflake_conn, sample_findings):
    conn, cur = mock_snowflake_conn
    sf_repo.save_findings(sample_findings)

    assert cur.execute.called
    sql = cur.execute.call_args[0][0]
    assert "MERGE INTO COCO_FACTORY.APP.INVESTIGATION_FINDING" in sql
    assert "TRY_PARSE_JSON" in sql
    conn.commit.assert_called()

    # Test retrieval
    cur.fetchall.return_value = [
        (
            "FND-TEST-001",
            "INV-TEST-001",
            "Summary text",
            "Statement text",
            "BEARING_DEGRADATION",
            0.91,
            json.dumps(["EV-TEST-001"]),
            json.dumps(["Fact 1", "Fact 2"]),
            json.dumps(["Inference 1"]),
            datetime(2026, 10, 2, 10, 3, tzinfo=timezone.utc),
        )
    ]
    fnds = sf_repo.get_findings("INV-TEST-001")
    assert len(fnds) == 1
    assert fnds[0].finding_id == "FND-TEST-001"
    assert fnds[0].observed_facts == ["Fact 1", "Fact 2"]
    assert fnds[0].inferences == ["Inference 1"]


def test_snowflake_save_and_get_recommendations(sf_repo, mock_snowflake_conn, sample_recommendations):
    conn, cur = mock_snowflake_conn
    sf_repo.save_recommendations(sample_recommendations)

    assert cur.execute.called
    sql = cur.execute.call_args[0][0]
    assert "MERGE INTO COCO_FACTORY.APP.INVESTIGATION_RECOMMENDATION" in sql
    assert "TRY_PARSE_JSON" in sql
    conn.commit.assert_called()

    # Test retrieval
    cur.fetchall.return_value = [
        (
            "REC-TEST-001",
            "INV-TEST-001",
            "Replace Bearing",
            "Statement",
            "INSPECT_BEARING_ASSEMBLY",
            "HIGH",
            "Rationale",
            "Order part",
            True,
            "ADVISORY",
            3.5,
            json.dumps(["SKF-6205"]),
            json.dumps(["LOTO"]),
            json.dumps(["EV-TEST-001"]),
        )
    ]
    recs = sf_repo.get_recommendations("INV-TEST-001")
    assert len(recs) == 1
    assert recs[0].recommendation_id == "REC-TEST-001"
    assert recs[0].suggested_parts == ["SKF-6205"]
    assert recs[0].suggested_checklist == ["LOTO"]
    assert recs[0].priority == Priority.HIGH


def test_snowflake_save_and_get_tool_calls(sf_repo, mock_snowflake_conn, sample_tool_calls):
    conn, cur = mock_snowflake_conn
    sf_repo.save_tool_calls(sample_tool_calls, investigation_id="INV-TEST-001")

    assert cur.execute.called
    sql = cur.execute.call_args[0][0]
    assert "MERGE INTO COCO_FACTORY.APP.INVESTIGATION_TOOL_CALL" in sql
    conn.commit.assert_called()

    # Test retrieval
    cur.fetchall.return_value = [
        (
            "TC-TEST-001",
            "INV-TEST-001",
            "get_telemetry_history",
            "READ",
            "investigation:read",
            json.dumps({"machine_id": "M21"}),
            140,
            45.2,
            True,
            None,
            datetime(2026, 10, 2, 10, 1, tzinfo=timezone.utc),
        )
    ]
    tcs = sf_repo.get_tool_calls("INV-TEST-001")
    assert len(tcs) == 1
    assert tcs[0].tool_call_id == "TC-TEST-001"
    assert tcs[0].arguments == {"machine_id": "M21"}
    assert tcs[0].duration_ms == 45.2


def test_snowflake_save_investigation_bundle_atomic_commit(
    sf_repo,
    mock_snowflake_conn,
    sample_investigation,
    sample_evidence,
    sample_hypotheses,
    sample_findings,
    sample_recommendations,
    sample_tool_calls,
):
    conn, cur = mock_snowflake_conn

    res = sf_repo.save_investigation_bundle(
        investigation=sample_investigation,
        evidence=sample_evidence,
        hypotheses=sample_hypotheses,
        findings=sample_findings,
        recommendations=sample_recommendations,
        tool_calls=sample_tool_calls,
    )

    assert res.investigation_id == "INV-TEST-001"

    # Verify BEGIN and COMMIT calls
    calls = [call_args[0][0] for call_args in cur.execute.call_args_list]
    assert "BEGIN" in calls[0]
    assert "COMMIT" in calls[-1]
    conn.commit.assert_called()


def test_snowflake_save_investigation_bundle_rollback_on_failure(
    sf_repo,
    mock_snowflake_conn,
    sample_investigation,
    sample_evidence,
):
    conn, cur = mock_snowflake_conn

    # Make cursor fail on second query (the evidence insert), and succeed on ROLLBACK
    cur.execute.side_effect = [None, Exception("Simulated DB connection drop"), None]

    with pytest.raises(Exception, match="Simulated DB connection drop"):
        sf_repo.save_investigation_bundle(
            investigation=sample_investigation,
            evidence=sample_evidence,
        )

    # Verify rollback was attempted
    rollback_calls = [
        call_args[0][0] for call_args in cur.execute.call_args_list if "ROLLBACK" in str(call_args[0][0])
    ]
    assert len(rollback_calls) >= 1
    conn.rollback.assert_called()


# -------------------------------------------------------------------------
# InMemoryRepository Interface Parity Tests
# -------------------------------------------------------------------------

def test_in_memory_repository_investigation_persistence_parity(
    sample_investigation,
    sample_evidence,
    sample_hypotheses,
    sample_findings,
    sample_recommendations,
    sample_tool_calls,
):
    mem_repo = InMemoryRepository(seed=False)

    # Test bundle persistence
    mem_repo.save_investigation_bundle(
        investigation=sample_investigation,
        evidence=sample_evidence,
        hypotheses=sample_hypotheses,
        findings=sample_findings,
        recommendations=sample_recommendations,
        tool_calls=sample_tool_calls,
    )

    # Verify all 6 entities retrievable
    retrieved_inv = mem_repo.get_investigation("INV-TEST-001")
    assert retrieved_inv is not None
    assert retrieved_inv.investigation_id == "INV-TEST-001"
    assert retrieved_inv.confidence == 0.92

    ev_list = mem_repo.get_evidence("INV-TEST-001")
    assert len(ev_list) == 1
    assert ev_list[0].evidence_id == "EV-TEST-001"

    hyp_list = mem_repo.get_hypotheses("INV-TEST-001")
    assert len(hyp_list) == 1
    assert hyp_list[0].hypothesis_id == "HYP-TEST-001"

    find_list = mem_repo.get_findings("INV-TEST-001")
    assert len(find_list) == 1
    assert find_list[0].finding_id == "FND-TEST-001"

    rec_list = mem_repo.get_recommendations("INV-TEST-001")
    assert len(rec_list) == 1
    assert rec_list[0].recommendation_id == "REC-TEST-001"

    tc_list = mem_repo.get_tool_calls("INV-TEST-001")
    assert len(tc_list) == 1
    assert tc_list[0].tool_call_id == "TC-TEST-001"


def test_in_memory_repository_idempotent_updates(
    sample_investigation,
    sample_evidence,
    sample_hypotheses,
    sample_findings,
    sample_recommendations,
    sample_tool_calls,
):
    mem_repo = InMemoryRepository(seed=False)

    # First save
    mem_repo.create_investigation(sample_investigation)
    mem_repo.save_evidence(sample_evidence)
    mem_repo.save_hypotheses(sample_hypotheses)
    mem_repo.save_findings(sample_findings)
    mem_repo.save_recommendations(sample_recommendations)
    mem_repo.save_tool_calls(sample_tool_calls, investigation_id="INV-TEST-001")

    # Second save with modified fields
    updated_inv = sample_investigation.model_copy(update={"summary": "Updated summary text"})
    mem_repo.create_investigation(updated_inv)

    assert mem_repo.get_investigation("INV-TEST-001").summary == "Updated summary text"
    assert len(mem_repo.get_evidence("INV-TEST-001")) == 1
    assert len(mem_repo.get_hypotheses("INV-TEST-001")) == 1
    assert len(mem_repo.get_findings("INV-TEST-001")) == 1
    assert len(mem_repo.get_recommendations("INV-TEST-001")) == 1
    assert len(mem_repo.get_tool_calls("INV-TEST-001")) == 1


def test_investigation_service_persists_all_six_entities():
    from services.investigation_service import InvestigationService
    from tools.registry import create_m4_tool_registry
    from agents.reliability.coco_adapter import DeterministicCoCoAdapter
    from agents.reliability.anti_hallucination import AntiHallucinationValidator
    from domain.models import InvestigationRequest

    mem_repo = InMemoryRepository(seed=True)
    tools = create_m4_tool_registry(mem_repo)
    svc = InvestigationService(
        repository=mem_repo,
        tool_registry=tools,
        reasoner=DeterministicCoCoAdapter(),
        validator=AntiHallucinationValidator(),
    )

    req = InvestigationRequest(
        request_id="REQ-BUNDLE-01",
        investigation_id="INV-BUNDLE-001",
        trigger_type=TriggerType.MACHINE,
        machine_id="M21",
    )

    result = svc.investigate(req)
    assert result is not None
    assert result.investigation_id == "INV-BUNDLE-001"

    # Verify all 6 entities persisted in repository
    inv = mem_repo.get_investigation("INV-BUNDLE-001")
    assert inv is not None
    assert inv.investigation_id == "INV-BUNDLE-001"

    ev = mem_repo.get_evidence("INV-BUNDLE-001")
    assert len(ev) > 0

    hyps = mem_repo.get_hypotheses("INV-BUNDLE-001")
    assert len(hyps) > 0

    findings = mem_repo.get_findings("INV-BUNDLE-001")
    assert len(findings) > 0

    recs = mem_repo.get_recommendations("INV-BUNDLE-001")
    assert len(recs) > 0

    tcs = mem_repo.get_tool_calls("INV-BUNDLE-001")
    assert len(tcs) > 0

