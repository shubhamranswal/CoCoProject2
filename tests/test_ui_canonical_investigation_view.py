"""Tests for Canonical Streamlit AI Investigation Workspace Modernization (M6.5.5.2).

Validates all 14 specified UI presentation criteria:
1. Header displays target equipment with dynamic asset name, machine ID, status, failure mode, confidence %, trigger info, and timestamps.
2. Zero hardcoded M204 / Conveyor Motor / ALT-M204 leakage for M21 investigation.
3. Provenance card displays adapter, execution mode, model name, evidence base count, and tool count.
4. Dynamic timeline renders progression grounded in actual investigation data without M204 strings.
5. Evidence panel renders all canonical categories (SENSOR, PREDICTION, FAILURE_HISTORY, MAINTENANCE, INVENTORY, PRODUCTION, KNOWLEDGE).
6. Evidence panel displays typed attributes (evidence_id, category, source_type, source_id, metric, observed_value, unit, severity, relationship, claim, summary, source_reference).
7. Zero emojis across all cards, badges, and components.
8. Hypotheses panel renders hypothesis_name, statement, confidence, status, rationale, and supporting/contradicting evidence badges.
9. Multi-finding panel renders all persisted findings (Root Cause, Operational Impact, Inventory Risk) with facts and inferences.
10. Advisory recommendation panel displays STATUS: ADVISORY (NON-EXECUTABLE), priority, action_type, suggested_next_step, suggested_parts, suggested_checklist, estimated_downtime_hours.
11. Zero execution buttons on recommendation panel.
12. Governed tool audit drawer renders tool name, mode, status, duration, and timestamp.
13. Approval panel correctly reports "No action proposals currently require human approval." when approval is None.
14. Both Light and Dark theme modes render cleanly without exceptions in AppTest.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
from streamlit.testing.v1 import AppTest

from app.streamlit.components.evidence import render_evidence_panel
from app.streamlit.components.timelines import render_investigation_timeline
from app.streamlit.services.view_service import CommandCenterFacade
from app.streamlit.views.investigations import render_investigations_view
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
    Machine,
    Recommendation,
    ToolCall,
)


APP_PATH = str((Path(__file__).parent.parent / "app" / "streamlit_app.py").resolve())


def _create_canonical_m21_bundle() -> Dict[str, Any]:
    """Build a complete canonical M21 investigation bundle matching authoritative state."""
    machine = Machine(
        machine_id="M21",
        line_id="LINE-02",
        machine_code="M21",
        name="Grinding Machine 21",
        asset_type="GRINDER",
        model="GRIND-X500",
        criticality="CRITICAL",
    )

    inv = Investigation(
        investigation_id="INV-M21-20261002-001",
        trigger_type=TriggerType.PREDICTION,
        trigger_id="TRG-M21-PRED-01",
        prediction_id="PRED-M21-20261002",
        machine_id="M21",
        component_id="C-M21-BEAR-DE",
        status=InvestigationStatus.COMPLETED,
        failure_mode=FailureMode.BEARING_DEGRADATION,
        confidence=0.95,
        created_at=datetime(2026, 10, 2, 14, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 10, 2, 14, 2, 30, tzinfo=timezone.utc),
        provenance={
            "adapter": "LiveCortexCoCoAdapter",
            "execution_mode": "LIVE_CORTEX",
            "model": "llama3.1-70b",
            "evidence_count": 11,
            "tool_count": 13,
        },
    )

    evidence_items = [
        Evidence(
            evidence_id="EV-S-M21-VIB--001",
            investigation_id=inv.investigation_id,
            evidence_type="TELEMETRY",
            category="SENSOR",
            source="sensor_telemetry",
            source_type="SENSOR",
            source_id="S-M21-VIB",
            metric="vibration_rms",
            claim="Vibration RMS is critically elevated above standard baseline.",
            observed_value=4.82,
            unit="mm/s",
            severity="HIGH",
            relationship="SUPPORTS",
            machine_id="M21",
            component_id="C-M21-BEAR-DE",
            source_reference="CORE.SENSOR_TELEMETRY",
            summary="Vibration RMS of 4.82 mm/s on drive-end bearing exceeds 2.80 mm/s baseline.",
        ),
        Evidence(
            evidence_id="EV-S-M21-BTMP--001",
            investigation_id=inv.investigation_id,
            evidence_type="TELEMETRY",
            category="SENSOR",
            source="sensor_telemetry",
            source_type="SENSOR",
            source_id="S-M21-BTMP",
            metric="bearing_temperature",
            claim="Drive-end bearing temperature is elevated.",
            observed_value=84.5,
            unit="deg_C",
            severity="MEDIUM",
            relationship="SUPPORTS",
            machine_id="M21",
            component_id="C-M21-BEAR-DE",
            source_reference="CORE.SENSOR_TELEMETRY",
            summary="Drive-end bearing temperature reached 84.5 deg_C.",
        ),
        Evidence(
            evidence_id="EV-PRED-M21-001",
            investigation_id=inv.investigation_id,
            evidence_type="RISK",
            category="PREDICTION",
            source="ml_risk_models",
            source_type="MODEL",
            source_id="PRED-M21-20261002",
            metric="failure_probability",
            claim="ML model predicts imminent bearing raceway failure.",
            observed_value=0.91,
            unit="probability",
            severity="CRITICAL",
            relationship="SUPPORTS",
            machine_id="M21",
            source_reference="ML.FAILURE_PREDICTION",
            summary="91% failure probability within 48 operating hours.",
        ),
        Evidence(
            evidence_id="EV-PRED-M21-RUL-002",
            investigation_id=inv.investigation_id,
            evidence_type="RISK",
            category="PREDICTION",
            source="ml_risk_models",
            source_type="MODEL",
            source_id="PRED-M21-20261002",
            metric="remaining_useful_life",
            claim="Remaining useful life is severely compressed.",
            observed_value=36.0,
            unit="hours",
            severity="HIGH",
            relationship="SUPPORTS",
            machine_id="M21",
            source_reference="ML.RUL_ESTIMATION",
            summary="RUL estimated at 36.0 hours before functional loss.",
        ),
        Evidence(
            evidence_id="EV-HIST-M21-001",
            investigation_id=inv.investigation_id,
            evidence_type="FAILURE_HISTORY",
            category="FAILURE_HISTORY",
            source="failure_records",
            source_type="WORK_ORDER",
            source_id="WO-HIST-2025-081",
            metric="spalling_precedent",
            claim="Machine M21 experienced identical inner-race spalling in 2025.",
            observed_value="INNER_RACE_SPALLING",
            unit="mode",
            severity="HIGH",
            relationship="SUPPORTS",
            machine_id="M21",
            source_reference="CORE.WORK_ORDER_HISTORY",
            summary="Historical replacement of drive-end spherical roller bearing after vibration spike.",
        ),
        Evidence(
            evidence_id="EV-MAINT-M21-001",
            investigation_id=inv.investigation_id,
            evidence_type="MAINTENANCE",
            category="MAINTENANCE",
            source="maintenance_logs",
            source_type="MAINTENANCE_LOG",
            source_id="LOG-2026-0902",
            metric="days_since_lubrication",
            claim="Last scheduled grease replenishment was performed 45 days ago.",
            observed_value=45,
            unit="days",
            severity="MEDIUM",
            relationship="SUPPORTS",
            machine_id="M21",
            source_reference="CORE.MAINTENANCE_LOG",
            summary="Grease service overdue per 30-day recommended interval.",
        ),
        Evidence(
            evidence_id="EV-INV-SP002-001",
            investigation_id=inv.investigation_id,
            evidence_type="INVENTORY",
            category="INVENTORY",
            source="erp_inventory",
            source_type="PART",
            source_id="SP-002",
            metric="stock_quantity",
            claim="Spherical roller bearing SP-002 stock level on site.",
            observed_value=2,
            unit="units",
            severity="LOW",
            relationship="SUPPORTS",
            source_reference="CORE.INVENTORY",
            summary="Two units of SP-002 available in central warehouse.",
        ),
        Evidence(
            evidence_id="EV-INV-SP002-002",
            investigation_id=inv.investigation_id,
            evidence_type="INVENTORY",
            category="INVENTORY",
            source="erp_inventory",
            source_type="PART",
            source_id="SP-002",
            metric="lead_time_days",
            claim="Replenishment lead time for replacement bearing.",
            observed_value=14,
            unit="days",
            severity="MEDIUM",
            relationship="CONTEXTUAL",
            source_reference="CORE.INVENTORY",
            summary="14-day vendor replenishment lead time if stock depleted.",
        ),
        Evidence(
            evidence_id="EV-INV-SP002-003",
            investigation_id=inv.investigation_id,
            evidence_type="INVENTORY",
            category="INVENTORY",
            source="erp_inventory",
            source_type="PART",
            source_id="SP-002",
            metric="unit_cost",
            claim="Unit replacement cost for SP-002 assembly.",
            observed_value=1450.0,
            unit="USD",
            severity="LOW",
            relationship="CONTEXTUAL",
            source_reference="CORE.INVENTORY",
            summary="Unit price $1,450.00 USD.",
        ),
        Evidence(
            evidence_id="EV-PROD-M21-001",
            investigation_id=inv.investigation_id,
            evidence_type="PRODUCTION",
            category="PRODUCTION",
            source="mes_schedule",
            source_type="SCHEDULE",
            source_id="SCHED-LINE02-W40",
            metric="hourly_downtime_cost",
            claim="Line 02 downtime cost during active grinding shift.",
            observed_value=18400.0,
            unit="USD/hr",
            severity="CRITICAL",
            relationship="SUPPORTS",
            machine_id="M21",
            source_reference="CORE.PRODUCTION_SCHEDULE",
            summary="Unscheduled stoppage costs $18,400.00/hour on Line 02.",
        ),
        Evidence(
            evidence_id="EV-KNOW-ISO-001",
            investigation_id=inv.investigation_id,
            evidence_type="DOCUMENT",
            category="KNOWLEDGE",
            source="technical_manual",
            source_type="MANUAL",
            source_id="ISO-10816-3",
            metric="vibration_severity_limit",
            claim="ISO 10816-3 Class II rigid machine vibration limits.",
            observed_value=4.5,
            unit="mm/s",
            severity="HIGH",
            relationship="SUPPORTS",
            source_reference="KNOWLEDGE.DOCUMENT_CHUNK#ISO-10816",
            summary="Zone C/D boundary is 4.5 mm/s; 4.82 mm/s triggers mandatory inspection.",
        ),
    ]

    hypotheses = [
        Hypothesis(
            hypothesis_id="HYP-01",
            investigation_id=inv.investigation_id,
            hypothesis_name="Drive-End Bearing Mechanical Degradation",
            statement="Machine M21 drive-end bearing is undergoing raceway spalling and progressive mechanical fatigue.",
            failure_mode=FailureMode.BEARING_DEGRADATION,
            confidence=0.94,
            status="SUPPORTED",
            rationale="Supported by elevated vibration RMS (4.82 mm/s), elevated temperature (84.5 deg_C), and ISO 10816-3 limits.",
            supporting_evidence_ids=["EV-S-M21-VIB--001", "EV-S-M21-BTMP--001", "EV-PRED-M21-001"],
            contradicting_evidence_ids=[],
        )
    ]

    findings = [
        Finding(
            finding_id="FIND-01",
            investigation_id=inv.investigation_id,
            summary="Progressive drive-end bearing mechanical distress confirmed on Machine M21.",
            statement="Vibration RMS and thermal signatures indicate advancing fatigue spalling on the inner raceway.",
            failure_mode=FailureMode.BEARING_DEGRADATION,
            confidence=0.94,
            evidence_refs=["EV-S-M21-VIB--001", "EV-S-M21-BTMP--001", "EV-PRED-M21-001"],
            observed_facts=[
                "Drive-end vibration RMS measured 4.82 mm/s, exceeding Zone C boundary (4.50 mm/s).",
                "Bearing operating temperature measured 84.5 deg_C.",
            ],
            historical_facts=[
                "Prior spherical roller bearing replacement occurred under matching vibration slope in August 2025.",
            ],
            inferences=[
                "Mechanical fatigue spalling is actively accelerating on the drive-end bearing raceway.",
            ],
        ),
        Finding(
            finding_id="FIND-02",
            investigation_id=inv.investigation_id,
            summary="Production revenue exposure of $18,400/hr in the event of unscheduled line stoppage.",
            statement="Failure to intervene within 36 hours risks functional line seizure and catastrophic yield loss.",
            failure_mode=FailureMode.BEARING_DEGRADATION,
            confidence=0.90,
            evidence_refs=["EV-PROD-M21-001", "EV-PRED-M21-RUL-002"],
            observed_facts=[
                "Production schedule SCHED-LINE02-W40 assigns critical path throughput to Machine M21.",
                "Hourly downtime loss rate is authoritative at $18,400.00/hr.",
            ],
            historical_facts=[],
            inferences=[
                "Planned maintenance window will prevent catastrophic unplanned outage.",
            ],
        ),
        Finding(
            finding_id="FIND-03",
            investigation_id=inv.investigation_id,
            summary="Spare part inventory risk: 2 units of SP-002 available with 14-day vendor lead time.",
            statement="Sufficient stock exists for immediate planned replacement, but inventory reservation is required.",
            failure_mode=FailureMode.BEARING_DEGRADATION,
            confidence=0.88,
            evidence_refs=["EV-INV-SP002-001", "EV-INV-SP002-002"],
            observed_facts=[
                "Central warehouse currently holds 2 units of spherical roller bearing SP-002.",
                "Supplier reorder lead time is 14 days.",
            ],
            historical_facts=[],
            inferences=[
                "Part reservation should be authorized immediately to prevent stockout.",
            ],
        ),
    ]

    recommendations = [
        Recommendation(
            recommendation_id="REC-01",
            investigation_id=inv.investigation_id,
            title="Inspect Drive-End Bearing Assembly",
            statement="Conduct governed physical inspection and scheduled replacement of SP-002 bearing assembly.",
            action_type="INSPECT_BEARING_ASSEMBLY",
            action_description="Execute lock-out tag-out, measure radial play clearance, inspect raceway condition, and replace bearing SP-002 if spalling exceeds threshold.",
            priority=Priority.HIGH,
            rationale="High vibration and thermal indicators suggest advancing raceway spalling.",
            suggested_next_step="Submit governed action proposal for human maintenance planner authorization.",
            action_required=True,
            status="ADVISORY",
            estimated_downtime_hours=2.0,
            suggested_parts=["SP-002"],
            suggested_checklist=[
                "Perform LOTO electrical and mechanical isolation on Machine M21.",
                "Measure drive-end bearing radial clearance using dial indicator.",
                "Inspect raceway and roller elements with borescope for micro-spalling.",
            ],
            evidence_refs=["EV-S-M21-VIB--001", "EV-S-M21-BTMP--001", "EV-INV-SP002-001"],
        )
    ]

    tool_calls = [
        ToolCall(
            tool_call_id=f"TC-M21-{i:03d}",
            execution_id=inv.investigation_id,
            tool_name="get_sensor_telemetry" if i % 2 == 0 else "get_machine_metadata",
            arguments={"machine_id": "M21", "tool_mode": "READ"},
            duration_ms=4.5 + (i * 0.5),
            is_success=True,
            started_at=datetime(2026, 10, 2, 14, 0, i, tzinfo=timezone.utc),
        )
        for i in range(1, 14)
    ]

    return {
        "investigation": inv,
        "machine": machine,
        "machine_name": machine.name,
        "evidence": evidence_items,
        "hypotheses": hypotheses,
        "findings": findings,
        "finding": findings[0],
        "recommendations": recommendations,
        "recommendation": recommendations[0],
        "provenance": inv.provenance,
        "tool_calls": tool_calls,
        "approval": None,
        "work_order": None,
    }


def _render_and_collect_html(
    facade_mock: Any,
    mock_df: Any = None,
    mock_exp: Any = None,
) -> str:
    """Helper to execute render_investigations_view and capture all markdown/html text."""
    rendered_chunks: List[str] = []

    def mock_markdown(body: str, unsafe_allow_html: bool = False) -> None:
        rendered_chunks.append(str(body))

    def mock_selectbox(label: str, options: list, index: int = 0, format_func: Any = None, key: str = "") -> str:
        return options[index] if options else ""

    col_mock = MagicMock()
    col_mock.__enter__.return_value = col_mock
    col_mock.__exit__.return_value = None

    def mock_columns(spec: Any) -> List[Any]:
        n = len(spec) if isinstance(spec, (list, tuple)) else int(spec)
        return [col_mock] * n

    df_patch = mock_df or MagicMock()
    exp_patch = mock_exp or MagicMock()
    exp_patch.return_value.__enter__.return_value = exp_patch
    exp_patch.return_value.__exit__.return_value = None

    with patch("streamlit.markdown", side_effect=mock_markdown), \
         patch("streamlit.selectbox", side_effect=mock_selectbox), \
         patch("streamlit.columns", side_effect=mock_columns), \
         patch("streamlit.dataframe", df_patch), \
         patch("streamlit.expander", exp_patch):
        render_investigations_view(facade_mock)

    return "\n".join(rendered_chunks)


class TestCanonicalInvestigationViewModernization:
    """Test suite for Milestone M6.5.5.2 AI Investigation workspace rendering."""

    @pytest.fixture
    def canonical_bundle(self) -> Dict[str, Any]:
        return _create_canonical_m21_bundle()

    @pytest.fixture
    def facade_mock(self, canonical_bundle: Dict[str, Any]) -> MagicMock:
        facade = MagicMock(spec=CommandCenterFacade)
        inv = canonical_bundle["investigation"]
        facade.get_investigations.return_value = [inv]
        facade.get_investigation_detail.return_value = canonical_bundle
        return facade

    def test_assertion_1_and_2_dynamic_header_and_zero_m204_leakage(
        self, facade_mock: MagicMock, canonical_bundle: Dict[str, Any]
    ) -> None:
        """Verify dynamic asset header renders M21 (Grinding Machine 21) with zero M204 leakage."""
        html = _render_and_collect_html(facade_mock)

        # Assertion 1: Dynamic asset name, machine ID, status, confidence, trigger info
        assert "ASSET: M21" in html
        assert "Grinding Machine 21" in html
        assert "Reliability Investigation - INV-M21-20261002-001" in html
        assert "BEARING_DEGRADATION" in html
        assert "95%" in html  # Confidence
        assert "PREDICTION" in html
        assert "PRED-M21-20261002" in html
        assert "Completed:" in html

        # Assertion 2: Zero hardcoded M204 strings
        assert "M204" not in html
        assert "Conveyor Drive Motor" not in html
        assert "ALT-M204" not in html

    def test_assertion_3_provenance_card_rendering(
        self, facade_mock: MagicMock, canonical_bundle: Dict[str, Any]
    ) -> None:
        """Verify compact provenance card displays adapter, mode, model, evidence and tool counts."""
        html = _render_and_collect_html(facade_mock)

        assert "Provenance & Execution:" in html
        assert "LIVE_CORTEX" in html
        assert "LiveCortexCoCoAdapter" in html
        assert "llama3.1-70b" in html
        assert "Evidence Base: <b>11</b>" in html
        assert "Governed Read Tools: <b>13</b>" in html

    def test_assertion_4_dynamic_progression_timeline_zero_m204(
        self, canonical_bundle: Dict[str, Any]
    ) -> None:
        """Verify timeline dynamically reflects M21 investigation without M204 strings."""
        rendered_chunks: List[str] = []

        with patch("streamlit.markdown", side_effect=lambda body, unsafe_allow_html=False: rendered_chunks.append(str(body))):
            render_investigation_timeline(canonical_bundle["investigation"], detail=canonical_bundle)

        html = "\n".join(rendered_chunks)
        assert "INVESTIGATION PROGRESSION" in html
        assert "Trigger Event Detected" in html
        assert "M21" in html
        assert "Grinding Machine 21" in html
        assert "Ingested and verified 11 evidence records" in html
        assert "Evaluated 1 diagnostic hypotheses" in html
        assert "Synthesized 3 findings" in html
        assert "INSPECT_BEARING_ASSEMBLY" in html
        assert "Advisory state maintained" in html
        assert "M204" not in html

    def test_assertion_5_and_6_evidence_panel_all_categories_and_typed_attributes(
        self, canonical_bundle: Dict[str, Any]
    ) -> None:
        """Verify evidence panel renders all canonical categories and typed metadata without emojis."""
        rendered_chunks: List[str] = []

        with patch("streamlit.markdown", side_effect=lambda body, unsafe_allow_html=False: rendered_chunks.append(str(body))), \
             patch("streamlit.selectbox", return_value="ALL"):
            render_evidence_panel(canonical_bundle["evidence"])

        html = "\n".join(rendered_chunks)

        # Assertion 5: All 7 canonical categories mapped
        for cat in ["SENSOR", "PREDICTION", "FAILURE_HISTORY", "MAINTENANCE", "INVENTORY", "PRODUCTION", "KNOWLEDGE"]:
            assert f">{cat}<" in html, f"Category badge for {cat} must be rendered"

        # Assertion 6: Typed attributes present
        assert "EV-S-M21-VIB--001" in html
        assert "mm/s" in html
        assert "deg_C" in html
        assert "S-M21-VIB" in html
        assert "CORE.SENSOR_TELEMETRY" in html
        assert "SUPPORTS" in html
        assert "HIGH" in html

    def test_assertion_7_zero_emojis(self, facade_mock: MagicMock) -> None:
        """Verify zero emojis are rendered across the entire investigation view."""
        html = _render_and_collect_html(facade_mock)

        # Check against common emoji ranges
        emoji_indicators = ["🔍", "⚙️", "✅", "❌", "⚠️", "🚨", "📊", "📋", "🔧", "⚡", "🕒", "🤖"]
        for emoji in emoji_indicators:
            assert emoji not in html, f"Found disallowed emoji {emoji} in UI rendering"

    def test_assertion_8_hypotheses_evaluation_statement_and_evidence_refs(
        self, facade_mock: MagicMock
    ) -> None:
        """Verify hypotheses section renders hypothesis name, statement, confidence, and evidence refs."""
        html = _render_and_collect_html(facade_mock)

        assert "Drive-End Bearing Mechanical Degradation" in html
        assert "Machine M21 drive-end bearing is undergoing raceway spalling" in html
        assert "94% conf" in html
        assert "SUPPORTED" in html
        assert "SUPPORTS: EV-S-M21-VIB--001" in html
        assert "SUPPORTS: EV-S-M21-BTMP--001" in html

    def test_assertion_9_multi_finding_panel(self, facade_mock: MagicMock) -> None:
        """Verify all 3 findings (Root Cause + Operational + Inventory) are rendered."""
        html = _render_and_collect_html(facade_mock)

        assert "Synthesized Investigation Findings (3 Findings)" in html
        assert "ROOT CAUSE FINDING (CONFIDENCE: 94%)" in html
        assert "Progressive drive-end bearing mechanical distress" in html
        assert "Production revenue exposure of $18,400/hr" in html
        assert "Spare part inventory risk: 2 units of SP-002" in html
        assert "Observed Sensor Facts:" in html
        assert "Historical Precedents:" in html
        assert "Correlated Inferences:" in html
        assert "4.82 mm/s" in html
        assert "14 days" in html

    def test_assertion_10_and_11_advisory_recommendation_zero_execution_buttons(
        self, facade_mock: MagicMock
    ) -> None:
        """Verify recommendation is explicitly ADVISORY (NON-EXECUTABLE) with zero execution buttons."""
        html = _render_and_collect_html(facade_mock)

        # Assertion 10: Advisory recommendation attributes
        assert "Advisory Recommendations (1 Items)" in html
        assert "STATUS: ADVISORY (NON-EXECUTABLE)" in html
        assert "PRIORITY: HIGH" in html
        assert "ACTION: INSPECT_BEARING_ASSEMBLY" in html
        assert "Est. Downtime: <b>2.0h</b>" in html
        assert "Inspect Drive-End Bearing Assembly" in html
        assert "Suggested Next Step:" in html
        assert "Submit governed action proposal" in html
        assert "Required / Suggested Parts: <b>SP-002</b>" in html
        assert "Suggested Procedure Checklist:" in html
        assert "Perform LOTO electrical and mechanical isolation" in html

        # Assertion 11: Zero execution buttons
        assert "Execute Action" not in html
        assert "Approve and Execute" not in html
        assert "Dispatch Work Order" not in html

    def test_assertion_12_governed_tool_audit_drawer(self, facade_mock: MagicMock) -> None:
        """Verify Governed Read Tool Audit Ledger expander renders tool calls."""
        mock_df = MagicMock()
        mock_exp = MagicMock()
        mock_exp.return_value.__enter__.return_value = mock_exp
        mock_exp.return_value.__exit__.return_value = None

        _render_and_collect_html(facade_mock, mock_df=mock_df, mock_exp=mock_exp)

        # Expander should be created with count
        mock_exp.assert_called_with("Governed Read Tool Audit Ledger (13 Invocations)", expanded=False)
        assert mock_df.called
        called_rows = mock_df.call_args[0][0]
        assert len(called_rows) == 13
        assert called_rows[0]["Tool"] in ["get_sensor_telemetry", "get_machine_metadata"]
        assert called_rows[0]["Mode"] == "READ"
        assert "PASS" in called_rows[0]["Status"]

    def test_assertion_13_governance_approval_panel_reports_no_proposals(
        self, facade_mock: MagicMock
    ) -> None:
        """Verify approval gateway cleanly reports no action proposals requiring human approval."""
        with patch("streamlit.info") as mock_info:
            _render_and_collect_html(facade_mock)
            mock_info.assert_called_with("No action proposals currently require human approval.")

    def test_assertion_14_both_themes_render_in_apptest(self) -> None:
        """Verify AI Investigations view renders without exception in both Light and Dark themes."""
        # Light theme test
        at_light = AppTest.from_file(APP_PATH)
        at_light.run(timeout=10)
        assert not at_light.exception
        at_light.session_state["theme_mode"] = "light"
        at_light.session_state["active_nav"] = "AI Investigations"
        at_light.run(timeout=10)
        assert not at_light.exception

        # Dark theme test
        at_dark = AppTest.from_file(APP_PATH)
        at_dark.run(timeout=10)
        assert not at_dark.exception
        at_dark.session_state["theme_mode"] = "dark"
        at_dark.session_state["active_nav"] = "AI Investigations"
        at_dark.run(timeout=10)
        assert not at_dark.exception

    def test_assertion_15_recommendation_rendering_zero_raw_html_code_block_leakage(
        self, facade_mock: MagicMock, canonical_bundle: Dict[str, Any]
    ) -> None:
        """Verify recommendation card rendering does NOT leak raw HTML markup as visible text.

        Tests canonical M21 recommendation shape (empty action_description, populated statement,
        suggested_next_step, suggested_parts, suggested_checklist).
        Ensures zero 4+ space indented code blocks, zero blank line HTML terminations,
        and that all semantic fields are cleanly and safely rendered.
        """
        import re

        # Configure canonical M21 recommendation shape matching live Snowflake
        rec = canonical_bundle["recommendations"][0]
        rec.action_description = ""  # Live Snowflake has no ACTION_DESCRIPTION column
        rec.statement = "Inspect the Drive-End Bearing Assembly on machine M21 to determine the extent of mechanical degradation."
        rec.suggested_next_step = "Conduct non-invasive acoustic/vibration check during scheduled shift transition; replacement should be considered only if inspection confirms defect."
        rec.suggested_parts = ["SP-002"]
        rec.suggested_checklist = [
            "Check bearing housing temperature with calibrated infrared thermometer",
            "Measure radial and axial vibration FFT spectra",
            "Inspect grease lubrication quality and contamination per DOC-001",
        ]

        markdown_calls: List[str] = []

        def capture_markdown(body: Any, *args: Any, **kwargs: Any) -> None:
            markdown_calls.append(str(body))

        with patch("streamlit.markdown", side_effect=capture_markdown), \
             patch("streamlit.selectbox", return_value="INV-M21-20261002-001"), \
             patch("streamlit.columns", side_effect=lambda s: [MagicMock()] * (len(s) if isinstance(s, (list, tuple)) else int(s))), \
             patch("streamlit.button", return_value=False), \
             patch("streamlit.dataframe"), \
             patch("streamlit.expander", return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock())):
            render_investigations_view(facade_mock)

        # Locate the recommendation card markdown call
        rec_cards = [call for call in markdown_calls if "border-left: 4px solid #0284c7;" in call]
        assert len(rec_cards) == 1, f"Expected exactly 1 recommendation card call, got {len(rec_cards)}"
        card_html = rec_cards[0]

        # 1. Verify NO line starts with 4+ spaces of indentation (which triggers CommonMark <pre><code>)
        lines = card_html.split("\n")
        for line_idx, line in enumerate(lines):
            assert not re.match(r"^[ ]{4,}", line), (
                f"Line {line_idx} has 4+ leading spaces which triggers an indented code block: {line!r}"
            )

        # 2. Verify NO internal blank lines between HTML elements
        for line_idx, line in enumerate(lines):
            if line_idx > 0 and line_idx < len(lines) - 1:
                assert line.strip() != "", f"Line {line_idx} is a blank line inside the HTML card: {line!r}"

        # 3. Verify semantic content remains fully visible
        assert "Inspect Drive-End Bearing Assembly" in card_html
        assert "STATUS: ADVISORY (NON-EXECUTABLE)" in card_html
        assert "PRIORITY: HIGH" in card_html
        assert "ACTION: INSPECT_BEARING_ASSEMBLY" in card_html
        assert "Inspect the Drive-End Bearing Assembly on machine M21" in card_html
        assert "Suggested Next Step:" in card_html
        assert "Conduct non-invasive acoustic/vibration check" in card_html
        assert "Required / Suggested Parts: <b>SP-002</b>" in card_html
        assert "Suggested Procedure Checklist:" in card_html
        assert "Check bearing housing temperature with calibrated infrared thermometer" in card_html
        assert "Measure radial and axial vibration FFT spectra" in card_html
        assert "Inspect grease lubrication quality and contamination per DOC-001" in card_html
        assert "EV-S-M21-VIB--001" in card_html

        # 4. Verify accidental HTML tags in semantic fields are stripped cleanly
        rec.suggested_next_step = "<div class='injected'><b>Perform acoustic check</b></div>"
        markdown_calls.clear()
        with patch("streamlit.markdown", side_effect=capture_markdown), \
             patch("streamlit.selectbox", return_value="INV-M21-20261002-001"), \
             patch("streamlit.columns", side_effect=lambda s: [MagicMock()] * (len(s) if isinstance(s, (list, tuple)) else int(s))), \
             patch("streamlit.button", return_value=False), \
             patch("streamlit.dataframe"), \
             patch("streamlit.expander", return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock())):
            render_investigations_view(facade_mock)

        sanitized_cards = [call for call in markdown_calls if "border-left: 4px solid #0284c7;" in call]
        assert len(sanitized_cards) == 1
        # The injected <div class='injected'> must have been stripped
        assert "<div class='injected'>" not in sanitized_cards[0]
        assert "Perform acoustic check" in sanitized_cards[0]

    def test_assertion_16_hypothesis_rendering_zero_raw_html_code_block_leakage(
        self, facade_mock: MagicMock, canonical_bundle: Dict[str, Any]
    ) -> None:
        """Verify hypothesis card rendering does NOT leak raw HTML markup as visible text.

        Tests canonical M21 hypothesis shape (empty/None rationale, populated statement,
        supporting_evidence_ids).
        Ensures zero 4+ space indented code blocks, zero blank line HTML terminations,
        and that all semantic fields are cleanly and safely rendered.
        """
        import re

        # Configure canonical M21 hypothesis shape matching live Snowflake (RATIONALE is NULL)
        hyp = canonical_bundle["hypotheses"][0]
        hyp.hypothesis_name = "Drive-End Bearing Mechanical Degradation"
        hyp.statement = "Machine M21 drive-end bearing is undergoing raceway spalling and progressive mechanical fatigue."
        hyp.rationale = None  # Live Snowflake has NULL rationale
        hyp.confidence = 0.85
        hyp.status = "SUPPORTED"
        hyp.supporting_evidence_ids = ["EV-S-M21-VIB--001", "EV-S-M21-BTMP--001", "EV-PRED-M21-001"]
        hyp.contradicting_evidence_ids = []

        markdown_calls: List[str] = []

        def capture_markdown(body: Any, *args: Any, **kwargs: Any) -> None:
            markdown_calls.append(str(body))

        with patch("streamlit.markdown", side_effect=capture_markdown), \
             patch("streamlit.selectbox", return_value="INV-M21-20261002-001"), \
             patch("streamlit.columns", side_effect=lambda s: [MagicMock()] * (len(s) if isinstance(s, (list, tuple)) else int(s))), \
             patch("streamlit.button", return_value=False), \
             patch("streamlit.dataframe"), \
             patch("streamlit.expander", return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock())):
            render_investigations_view(facade_mock)

        # Locate the hypothesis card markdown call
        hyp_cards = [call for call in markdown_calls if "Drive-End Bearing Mechanical Degradation" in call]
        assert len(hyp_cards) == 1, f"Expected exactly 1 hypothesis card call, got {len(hyp_cards)}"
        card_html = hyp_cards[0]

        # 1. Verify NO line starts with 4+ spaces of indentation (which triggers CommonMark <pre><code>)
        lines = card_html.split("\n")
        for line_idx, line in enumerate(lines):
            assert not re.match(r"^[ ]{4,}", line), (
                f"Line {line_idx} has 4+ leading spaces which triggers an indented code block: {line!r}"
            )

        # 2. Verify NO internal blank lines between HTML elements
        for line_idx, line in enumerate(lines):
            if line_idx > 0 and line_idx < len(lines) - 1:
                assert line.strip() != "", f"Line {line_idx} is a blank line inside the HTML card: {line!r}"

        # 3. Verify semantic content remains fully visible
        assert "Drive-End Bearing Mechanical Degradation" in card_html
        assert "Machine M21 drive-end bearing is undergoing raceway spalling" in card_html
        assert "85% conf" in card_html
        assert "SUPPORTED" in card_html
        assert "SUPPORTS: EV-S-M21-VIB--001" in card_html
        assert "SUPPORTS: EV-S-M21-BTMP--001" in card_html

        # 4. Verify empty optional rationale does NOT produce an empty <div> with blank lines
        assert 'color: var(--text-secondary); margin-top: 6px;"></div>' not in card_html
        assert 'color: var(--text-secondary); margin-top: 6px;">\n' not in card_html

        # 5. Verify populated optional rationale renders cleanly when present
        hyp.rationale = "Harmonic peak detected at 120Hz confirming bearing race spalling."
        markdown_calls.clear()
        with patch("streamlit.markdown", side_effect=capture_markdown), \
             patch("streamlit.selectbox", return_value="INV-M21-20261002-001"), \
             patch("streamlit.columns", side_effect=lambda s: [MagicMock()] * (len(s) if isinstance(s, (list, tuple)) else int(s))), \
             patch("streamlit.button", return_value=False), \
             patch("streamlit.dataframe"), \
             patch("streamlit.expander", return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock())):
            render_investigations_view(facade_mock)

        populated_cards = [call for call in markdown_calls if "Drive-End Bearing Mechanical Degradation" in call]
        assert len(populated_cards) == 1
        assert "Harmonic peak detected at 120Hz" in populated_cards[0]

        # 6. Verify accidental HTML tags in dynamic fields are sanitized
        hyp.statement = "<div class='malicious'>Malicious statement</div>"
        markdown_calls.clear()
        with patch("streamlit.markdown", side_effect=capture_markdown), \
             patch("streamlit.selectbox", return_value="INV-M21-20261002-001"), \
             patch("streamlit.columns", side_effect=lambda s: [MagicMock()] * (len(s) if isinstance(s, (list, tuple)) else int(s))), \
             patch("streamlit.button", return_value=False), \
             patch("streamlit.dataframe"), \
             patch("streamlit.expander", return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock())):
            render_investigations_view(facade_mock)

        sanitized_hyp = [call for call in markdown_calls if "Drive-End Bearing Mechanical Degradation" in call]
        assert len(sanitized_hyp) == 1
        assert "<div class='malicious'>" not in sanitized_hyp[0]
        assert "Malicious statement" in sanitized_hyp[0]
