"""Tests for LiveCortexCoCoAdapter truthful provenance, Cortex consumption, and fallback behavior (Milestone M6.5.3).

Validates:
1. Successful Cortex call -> Cortex JSON content actually consumed -> provenance LIVE_CORTEX.
2. Cortex query failure (exception/timeout) -> deterministic fallback -> provenance DETERMINISTIC_FALLBACK.
3. Cortex unconfigured (connection_mgr=None) -> deterministic fallback -> provenance DETERMINISTIC_FALLBACK.
4. Cortex disabled (enabled=False) -> deterministic fallback -> provenance DETERMINISTIC_FALLBACK.
5. Cortex returns empty/invalid output -> deterministic fallback -> provenance DETERMINISTIC_FALLBACK.
6. Cortex returns unsupported claims (hallucinated evidence IDs) -> anti-hallucination rejection -> DETERMINISTIC_FALLBACK.
7. Cortex returns non-advisory recommendation -> anti-hallucination rejection -> DETERMINISTIC_FALLBACK.
8. Provenance is strictly NEVER LIVE_CORTEX when fallback content was used.
9. InvestigationService end-to-end integration preserves truthful provenance into repository persistence.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest

from domain.enums import FailureMode, Priority, InvestigationStatus, TriggerType
from domain.models import (
    Evidence,
    InvestigationRequest,
)
from agents.reliability.coco_adapter import (
    InvestigationContext,
    LiveCortexCoCoAdapter,
    DeterministicCoCoAdapter,
)
from repositories.memory.memory_repository import InMemoryRepository
from services.investigation_service import InvestigationService
from tools.registry import create_m4_tool_registry
from agents.reliability.anti_hallucination import AntiHallucinationValidator


@pytest.fixture
def sample_evidence():
    return [
        Evidence(
            evidence_id="EV-SENS-01",
            investigation_id="INV-CTX-01",
            evidence_type="TELEMETRY",
            category="SENSOR",
            source="sensor",
            metric="vibration_rms",
            observed_value=8.2,
            unit="mm/s",
            severity="CRITICAL",
            relationship="SUPPORTS",
            machine_id="M21",
            component_id="C-M21-BRG",
            summary="Vibration RMS reached 8.2 mm/s",
            timestamp=datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc),
        ),
        Evidence(
            evidence_id="EV-PRED-01",
            investigation_id="INV-CTX-01",
            evidence_type="RISK",
            category="PREDICTION",
            source="model",
            metric="failure_probability",
            observed_value=0.91,
            unit="",
            severity="CRITICAL",
            relationship="SUPPORTS",
            machine_id="M21",
            component_id="C-M21-BRG",
            summary="ML predicted failure probability 0.91 within 7 days",
            timestamp=datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc),
        ),
    ]


@pytest.fixture
def investigation_context(sample_evidence):
    return InvestigationContext(
        investigation_id="INV-CTX-01",
        machine_id="M21",
        component_id="C-M21-BRG",
        trigger_type="PREDICTION",
        trigger_id="PRED-001",
        prediction={"prediction_id": "PRED-001", "failure_probability": 0.91},
        evidence_items=sample_evidence,
    )


@pytest.fixture
def mock_snowflake_connection():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    mgr = MagicMock()
    mgr.get_connection.return_value = conn
    return mgr, conn, cur


@pytest.fixture
def valid_cortex_json():
    return json.dumps({
        "summary": "Cortex analysis: Severe inner raceway spall confirmed on M21 bearing.",
        "hypotheses": [
            {
                "hypothesis_id": "HYP-M21-01",
                "hypothesis_name": "Inner Raceway Spalling",
                "statement": "Physical vibration peak and ML warning confirm accelerated race spalling.",
                "failure_mode": "BEARING_DEGRADATION",
                "confidence": 0.95,
                "supporting_evidence_ids": ["EV-SENS-01", "EV-PRED-01"],
                "status": "SUPPORTED",
                "rationale": "High vibration and high predictive risk converge on bearing fault."
            }
        ],
        "findings": [
            {
                "finding_id": "FIND-M21-01",
                "summary": "Cortex verified vibration RMS exceedance of 8.2 mm/s.",
                "statement": "Telemetry and ML predictions corroborate imminent bearing fatigue.",
                "failure_mode": "BEARING_DEGRADATION",
                "confidence": 0.96,
                "evidence_refs": ["EV-SENS-01", "EV-PRED-01"],
                "observed_facts": ["Vibration RMS at 8.2 mm/s", "ML probability 0.91"],
                "inferences": ["L10 bearing lifespan exhausted"]
            }
        ],
        "recommendations": [
            {
                "recommendation_id": "REC-M21-01",
                "title": "Advisory Bearing Replacement",
                "statement": "Plan replacement of drive-end bearing assembly C-M21-BRG.",
                "action_type": "INSPECT_BEARING_ASSEMBLY",
                "priority": "CRITICAL",
                "rationale": "Avoid unplanned line shutdown during upcoming shift.",
                "suggested_next_step": "Issue purchase order for SKF-6205-2RS.",
                "action_required": True,
                "status": "ADVISORY",
                "estimated_downtime_hours": 3.0,
                "suggested_parts": ["SKF-6205-2RS"],
                "suggested_checklist": ["LOTO", "Vibration baseline re-check"],
                "evidence_refs": ["EV-SENS-01", "EV-PRED-01"]
            }
        ],
        "limitations": ["Limited to 7 days telemetry"]
    })


# -------------------------------------------------------------------------
# Test Cases
# -------------------------------------------------------------------------

def test_cortex_successful_call_consumed_and_provenance_success(
    investigation_context, mock_snowflake_connection, valid_cortex_json
):
    mgr, conn, cur = mock_snowflake_connection
    cur.fetchone.return_value = (valid_cortex_json,)

    adapter = LiveCortexCoCoAdapter(connection_mgr=mgr)
    result = adapter.reason(investigation_context)

    # 1. SQL executed safely and parameterized
    cur.execute.assert_called_once()
    sql, params = cur.execute.call_args[0]
    assert "SNOWFLAKE.CORTEX.COMPLETE" in sql
    assert params[0] == "snowflake-arctic"

    # 2. Provenance is truthful LIVE_CORTEX
    assert result.provenance.get("execution_mode") == "LIVE_CORTEX"
    assert adapter.last_execution_mode == "LIVE_CORTEX"
    assert result.provenance.get("adapter") == "LiveCortexCoCoAdapter"

    # 3. Cortex content was ACTUALLY CONSUMED and returned (not fallback content)
    assert result.summary == "Cortex analysis: Severe inner raceway spall confirmed on M21 bearing."
    assert result.findings[0].summary == "Cortex verified vibration RMS exceedance of 8.2 mm/s."
    assert result.findings[0].confidence == 0.96
    assert result.recommendations[0].title == "Advisory Bearing Replacement"
    assert result.recommendations[0].priority == Priority.CRITICAL


def test_cortex_unavailable_connection_mgr_none(investigation_context):
    adapter = LiveCortexCoCoAdapter(connection_mgr=None)
    result = adapter.reason(investigation_context)

    assert result.provenance.get("execution_mode") == "DETERMINISTIC_FALLBACK"
    assert adapter.last_execution_mode == "DETERMINISTIC_FALLBACK"
    assert result.provenance.get("execution_mode") != "LIVE_CORTEX"
    # Verify explicit limitation added
    assert any("Cortex LLM not utilized" in lim for lim in result.limitations)


def test_cortex_explicitly_disabled(investigation_context, mock_snowflake_connection):
    mgr, conn, cur = mock_snowflake_connection
    adapter = LiveCortexCoCoAdapter(connection_mgr=mgr, enabled=False)
    result = adapter.reason(investigation_context)

    # Verify no connection called
    mgr.get_connection.assert_not_called()
    assert result.provenance.get("execution_mode") == "DETERMINISTIC_FALLBACK"
    assert adapter.last_execution_mode == "DETERMINISTIC_FALLBACK"
    assert any("Cortex integration explicitly disabled" in lim for lim in result.limitations)


def test_cortex_query_execution_failure(investigation_context, mock_snowflake_connection):
    mgr, conn, cur = mock_snowflake_connection
    cur.execute.side_effect = Exception("Snowflake warehouse COMPUTE_WH suspended")

    adapter = LiveCortexCoCoAdapter(connection_mgr=mgr)
    result = adapter.reason(investigation_context)

    assert result.provenance.get("execution_mode") == "DETERMINISTIC_FALLBACK"
    assert adapter.last_execution_mode == "DETERMINISTIC_FALLBACK"
    assert result.provenance.get("execution_mode") != "LIVE_CORTEX"
    assert any("COMPUTE_WH suspended" in lim for lim in result.limitations)


def test_cortex_returns_empty_or_whitespace_output(investigation_context, mock_snowflake_connection):
    mgr, conn, cur = mock_snowflake_connection
    cur.fetchone.return_value = ("   ",)

    adapter = LiveCortexCoCoAdapter(connection_mgr=mgr)
    result = adapter.reason(investigation_context)

    assert result.provenance.get("execution_mode") == "DETERMINISTIC_FALLBACK"
    assert adapter.last_execution_mode == "DETERMINISTIC_FALLBACK"
    assert result.provenance.get("execution_mode") != "LIVE_CORTEX"
    assert any("Cortex returned empty output" in lim for lim in result.limitations)


def test_cortex_returns_invalid_json_format(investigation_context, mock_snowflake_connection):
    mgr, conn, cur = mock_snowflake_connection
    cur.fetchone.return_value = ("I cannot generate JSON right now due to safety guidelines.",)

    adapter = LiveCortexCoCoAdapter(connection_mgr=mgr)
    result = adapter.reason(investigation_context)

    assert result.provenance.get("execution_mode") == "DETERMINISTIC_FALLBACK"
    assert adapter.last_execution_mode == "DETERMINISTIC_FALLBACK"
    assert result.provenance.get("execution_mode") != "LIVE_CORTEX"
    assert any("failed validation" in lim for lim in result.limitations)


def test_cortex_output_with_unsupported_evidence_rejected_by_anti_hallucination(
    investigation_context, mock_snowflake_connection
):
    mgr, conn, cur = mock_snowflake_connection
    # Inject hallucinated evidence ID EV-HALLUCINATED-999
    bad_cortex_json = json.dumps({
        "summary": "Hallucinated reasoning output",
        "hypotheses": [],
        "findings": [
            {
                "finding_id": "FIND-M21-01",
                "summary": "Finding with fake evidence",
                "failure_mode": "BEARING_DEGRADATION",
                "evidence_refs": ["EV-HALLUCINATED-999"],
            }
        ],
        "recommendations": [
            {
                "recommendation_id": "REC-M21-01",
                "title": "Advisory recommendation",
                "action_type": "INSPECT_BEARING_ASSEMBLY",
                "priority": "HIGH",
                "status": "ADVISORY",
                "evidence_refs": ["EV-SENS-01"],
            }
        ],
    })
    cur.fetchone.return_value = (bad_cortex_json,)

    adapter = LiveCortexCoCoAdapter(connection_mgr=mgr)
    result = adapter.reason(investigation_context)

    # Must be rejected and fall back to deterministic
    assert result.provenance.get("execution_mode") == "DETERMINISTIC_FALLBACK"
    assert adapter.last_execution_mode == "DETERMINISTIC_FALLBACK"
    assert result.provenance.get("execution_mode") != "LIVE_CORTEX"
    # Result must not contain the fake evidence ID
    assert "EV-HALLUCINATED-999" not in result.evidence_refs


def test_cortex_output_with_non_advisory_status_rejected(
    investigation_context, mock_snowflake_connection
):
    mgr, conn, cur = mock_snowflake_connection
    # Inject illegal non-advisory status or claimed executed action
    bad_cortex_json = json.dumps({
        "summary": "Illegal action claimed",
        "hypotheses": [],
        "findings": [
            {
                "finding_id": "FIND-M21-01",
                "summary": "Valid finding",
                "failure_mode": "BEARING_DEGRADATION",
                "evidence_refs": ["EV-SENS-01"],
            }
        ],
        "recommendations": [
            {
                "recommendation_id": "REC-M21-01",
                "title": "Work Order Executed",
                "statement": "Emergency work order created and dispatched to maintenance crew.",
                "action_type": "INSPECT_BEARING_ASSEMBLY",
                "priority": "HIGH",
                "status": "EXECUTED",  # Strictly forbidden
                "evidence_refs": ["EV-SENS-01"],
            }
        ],
    })
    cur.fetchone.return_value = (bad_cortex_json,)

    adapter = LiveCortexCoCoAdapter(connection_mgr=mgr)
    result = adapter.reason(investigation_context)

    # Must be rejected and fall back to deterministic
    assert result.provenance.get("execution_mode") == "DETERMINISTIC_FALLBACK"
    assert adapter.last_execution_mode == "DETERMINISTIC_FALLBACK"
    assert result.provenance.get("execution_mode") != "LIVE_CORTEX"
    assert result.recommendations[0].status == "ADVISORY"


def test_investigation_service_persists_truthful_cortex_provenance(
    mock_snowflake_connection,
):
    mgr, conn, cur = mock_snowflake_connection

    def fake_execute(sql, params):
        import re
        prompt = params[1]
        match = re.search(r"Valid Evidence IDs: (\[.*?\])", prompt)
        ev_ids = json.loads(match.group(1).replace("'", '"')) if match else ["EV-SENS-01"]
        sample_ev = ev_ids[:2]
        cortex_payload = {
            "summary": "Live Cortex investigation completed for M21.",
            "hypotheses": [
                {
                    "hypothesis_id": "HYP-M21-01",
                    "hypothesis_name": "Bearing Spalling",
                    "failure_mode": "BEARING_DEGRADATION",
                    "confidence": 0.94,
                    "supporting_evidence_ids": sample_ev,
                    "status": "SUPPORTED",
                    "rationale": "High vibration and risk converge on mechanical fault."
                }
            ],
            "findings": [
                {
                    "finding_id": "FIND-M21-01",
                    "summary": "Cortex verified sensor telemetry exceedances",
                    "failure_mode": "BEARING_DEGRADATION",
                    "confidence": 0.95,
                    "evidence_refs": sample_ev,
                    "observed_facts": ["Vibration exceedance"],
                    "inferences": ["Accelerated bearing wear"]
                }
            ],
            "recommendations": [
                {
                    "recommendation_id": "REC-M21-01",
                    "title": "Advisory Bearing Overhaul",
                    "statement": "Schedule physical inspection of bearing assembly.",
                    "action_type": "INSPECT_BEARING_ASSEMBLY",
                    "priority": "HIGH",
                    "rationale": "Proactive inspection to prevent unplanned stoppage.",
                    "suggested_next_step": "Check bearing lubrication.",
                    "status": "ADVISORY",
                    "evidence_refs": sample_ev
                }
            ],
            "limitations": []
        }
        cur.fetchone.return_value = (json.dumps(cortex_payload),)

    cur.execute.side_effect = fake_execute

    mem_repo = InMemoryRepository(seed=True)
    tools = create_m4_tool_registry(mem_repo)
    adapter = LiveCortexCoCoAdapter(connection_mgr=mgr)
    svc = InvestigationService(
        repository=mem_repo,
        tool_registry=tools,
        reasoner=adapter,
        validator=AntiHallucinationValidator(),
    )

    req = InvestigationRequest(
        request_id="REQ-CORTEX-01",
        investigation_id="INV-CORTEX-001",
        trigger_type=TriggerType.MACHINE,
        machine_id="M21",
    )

    res = svc.investigate(req)
    assert res is not None
    assert res.provenance.get("execution_mode") == "LIVE_CORTEX"

    persisted = mem_repo.get_investigation("INV-CORTEX-001")
    assert persisted is not None
    assert persisted.provenance.get("execution_mode") == "LIVE_CORTEX"
    assert persisted.provenance.get("model") == "snowflake-arctic"
