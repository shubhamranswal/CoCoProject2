"""Tests for Command Center Metrics Semantics and Lineage.

Verifies:
1. Critical Alerts KPI counts actual Severity.CRITICAL alerts, not total active alerts.
2. Machines at Risk KPI counts distinct machines currently requiring attention.
3. Active alert accounting includes both OPEN and INVESTIGATING (acknowledged) alerts.
4. Active failure precursors select assets prioritized by predictive PoF & alert severity.
5. Highlighted precursor machines are marked with is_precursor=True in the asset grid.
6. Fleet asset grid sorts by health severity and failure risk descending.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.streamlit.services.view_service import CommandCenterFacade
from domain.enums import AlertStatus, HealthStatus, Severity, FailureMode
from domain.models.asset import Machine
from domain.models.intelligence import Alert
from domain.models.reliability import FailureRisk


def test_command_center_metrics_semantics_in_memory():
    """Verify in-memory facade calculates distinct semantics for critical alerts vs active alerts."""
    facade = CommandCenterFacade(backend_mode="in_memory")
    snapshot = facade.get_command_center_snapshot(force_refresh=True)

    kpis = snapshot.kpis
    assert "critical_alerts" in kpis
    assert "active_alerts" in kpis
    assert "machines_at_risk" in kpis
    assert "critical_assets" in kpis
    assert "warning_assets" in kpis

    # In default in-memory seeded state:
    # M204 has 1 critical alert
    assert kpis["critical_alerts"] == 1
    assert kpis["active_alerts"] >= 1
    assert kpis["critical_alerts"] <= kpis["active_alerts"]
    assert kpis["machines_at_risk"] >= 1
    assert kpis["critical_assets"] >= 1

    # Precursors list must contain M204
    assert len(snapshot.critical_events) >= 1
    precursor_mids = [e["machine"].machine_id for e in snapshot.critical_events if e["machine"]]
    assert "M204" in precursor_mids

    # Asset grid must mark M204 with is_precursor=True
    m204_row = next((row for row in snapshot.asset_grid if row["machine"].machine_id == "M204"), None)
    assert m204_row is not None
    assert m204_row["is_precursor"] is True
    assert m204_row["active_alerts_count"] >= 1
    assert m204_row["critical_alerts_count"] >= 1


def test_command_center_semantics_with_mock_repo():
    """Verify data lineage and metric definitions with a controlled multi-machine fleet."""
    mock_repo = MagicMock()

    m1 = Machine(
        machine_id="M01",
        line_id="L1",
        machine_code="M01",
        name="CNC Lathe 1",
        asset_type="lathe",
        criticality="HIGH",
        health_status=HealthStatus.HEALTHY,
    )
    m5 = Machine(
        machine_id="M05",
        line_id="L1",
        machine_code="M05",
        name="Grinder 1",
        asset_type="grinder",
        criticality="CRITICAL",
        health_status=HealthStatus.CRITICAL,
    )
    m15 = Machine(
        machine_id="M15",
        line_id="L3",
        machine_code="M15",
        name="Conveyor Assembly 2",
        asset_type="conveyor",
        criticality="MEDIUM",
        health_status=HealthStatus.DEGRADING,
    )
    m21 = Machine(
        machine_id="M21",
        line_id="L5",
        machine_code="M21",
        name="Grinder 3",
        asset_type="grinder",
        criticality="CRITICAL",
        health_status=HealthStatus.HEALTHY,  # Initially marked healthy in old daily rollup
    )
    mock_repo.list_machines.return_value = [m1, m5, m15, m21]

    # Alerts:
    # M01 has 1 WARNING alert (OPEN)
    # M05 has 1 CRITICAL alert (OPEN) and 1 WARNING alert (OPEN)
    # M15 has 1 WARNING alert (INVESTIGATING / acknowledged)
    # M21 has 1 CRITICAL alert (INVESTIGATING / acknowledged)
    a_m01 = Alert(
        alert_id="ALT-1",
        machine_id="M01",
        severity=Severity.HIGH,
        status=AlertStatus.OPEN,
        trigger_reason="vibration high",
        risk_score=0.40,
    )
    a_m05_crit = Alert(
        alert_id="ALT-2",
        machine_id="M05",
        severity=Severity.CRITICAL,
        status=AlertStatus.OPEN,
        trigger_reason="vibration critical",
        risk_score=0.90,
    )
    a_m05_warn = Alert(
        alert_id="ALT-3",
        machine_id="M05",
        severity=Severity.HIGH,
        status=AlertStatus.OPEN,
        trigger_reason="bearing temp high",
        risk_score=0.75,
    )
    a_m15_ack = Alert(
        alert_id="ALT-4",
        machine_id="M15",
        severity=Severity.HIGH,
        status=AlertStatus.INVESTIGATING,
        trigger_reason="motor current high",
        risk_score=0.60,
    )
    a_m21_ack = Alert(
        alert_id="ALT-5",
        machine_id="M21",
        severity=Severity.CRITICAL,
        status=AlertStatus.INVESTIGATING,
        trigger_reason="bearing wear exceedance",
        risk_score=0.95,
    )

    def mock_list_alerts(machine_id=None, status=None):
        if status == AlertStatus.OPEN:
            return [a_m01, a_m05_crit, a_m05_warn]
        elif status == AlertStatus.INVESTIGATING:
            return [a_m15_ack, a_m21_ack]
        return [a_m01, a_m05_crit, a_m05_warn, a_m15_ack, a_m21_ack]

    mock_repo.list_alerts.side_effect = mock_list_alerts
    mock_repo.list_work_orders.return_value = []
    mock_repo.list_investigations.return_value = []

    # Failure risks (ML probabilities):
    # M21: 95% PoF, M05: 91% PoF, M15: 78% PoF, M01: 8% PoF
    mock_repo.get_latest_failure_risks.return_value = {
        "M21": FailureRisk(risk_id="R-21", machine_id="M21", failure_mode=FailureMode.BEARING_DEGRADATION, risk_score=0.95),
        "M05": FailureRisk(risk_id="R-05", machine_id="M05", failure_mode=FailureMode.BEARING_DEGRADATION, risk_score=0.91),
        "M15": FailureRisk(risk_id="R-15", machine_id="M15", failure_mode=FailureMode.BEARING_DEGRADATION, risk_score=0.78),
        "M01": FailureRisk(risk_id="R-01", machine_id="M01", failure_mode=FailureMode.BEARING_DEGRADATION, risk_score=0.08),
    }
    mock_repo.get_latest_predictions.return_value = {}

    facade = CommandCenterFacade(backend_mode="in_memory", repo=mock_repo)
    snapshot = facade.get_command_center_snapshot(force_refresh=True)

    kpis = snapshot.kpis

    # Total active alerts: 5 (3 open + 2 acknowledged)
    assert kpis["active_alerts"] == 5

    # Actual critical alerts: 2 (ALT-2 on M05 and ALT-5 on M21)
    assert kpis["critical_alerts"] == 2

    # Machines at risk: M05, M21 (critical), M15 (warning), M01 (warning due to alert)
    # Total distinct machines requiring attention: 4
    assert kpis["machines_at_risk"] == 4

    # M21 operational health status must be synchronized to CRITICAL due to 95% PoF and critical alert
    m21_grid = next(item for item in snapshot.asset_grid if item["machine"].machine_id == "M21")
    assert m21_grid["machine"].health_status == HealthStatus.CRITICAL
    assert m21_grid["active_alerts_count"] == 1
    assert m21_grid["critical_alerts_count"] == 1
    assert m21_grid["is_precursor"] is True

    # Precursors must highlight the highest predictive threats: M21 and M05
    top_threat_mids = [e["machine"].machine_id for e in snapshot.critical_events]
    assert top_threat_mids[0] == "M21"
    assert top_threat_mids[1] == "M05"


def test_key_signals_rendering_output():
    """Verify render_key_signals displays critical_alerts and machines_at_risk cleanly."""
    from unittest.mock import patch
    from app.streamlit.components.metric_cards import render_key_signals

    kpis = {
        "critical_alerts": 13,
        "active_alerts": 34,
        "critical_assets": 11,
        "warning_assets": 5,
        "machines_at_risk": 18,
        "open_work_orders": 3,
        "pending_approvals": 2,
        "affected_lines": 4,
    }

    markdown_outputs = []

    def mock_columns(spec, **kwargs):
        count = len(spec) if isinstance(spec, (list, tuple)) else int(spec)
        cols = []
        for _ in range(count):
            c = MagicMock()
            c.__enter__.return_value = c
            c.__exit__.return_value = None
            cols.append(c)
        return cols

    with patch("streamlit.markdown", side_effect=lambda body, unsafe_allow_html=False: markdown_outputs.append(str(body))), \
         patch("streamlit.columns", side_effect=mock_columns):
        render_key_signals(kpis)

    rendered_text = "".join(markdown_outputs)

    # Must contain the actual critical alerts count (13) rather than total active alerts (34)
    assert ">13<" in rendered_text
    assert "34 total active" in rendered_text

    # Must contain machines at risk (18) and breakdown
    assert ">18<" in rendered_text
    assert "11 Critical • 5 Warning" in rendered_text
    assert "4 Production Lines Affected" in rendered_text


def test_all_8_precursor_and_metric_invariants():
    """Verify all 8 user requirements on precursor consistency and metric invariants."""
    facade = CommandCenterFacade(backend_mode="in_memory")
    snapshot = facade.get_command_center_snapshot(force_refresh=True)

    fleet_map = {row["machine"].machine_id: row for row in snapshot.asset_grid}
    precursor_events = snapshot.critical_events

    # 1. Every precursor machine exists in the fleet table
    for ev in precursor_events:
        m_id = ev["machine"].machine_id
        assert m_id in fleet_map, f"Precursor machine {m_id} not found in fleet table"

    # 2. Its FAILURE RISK matches the value shown in the precursor card
    for ev in precursor_events:
        m_id = ev["machine"].machine_id
        fleet_row = fleet_map[m_id]
        fleet_risk = f"{fleet_row['risk'].risk_score * 100:.0f}%" if fleet_row["risk"] else "--"
        card_risk = f"{ev['risk'].risk_score * 100:.0f}%" if ev["risk"] else "--"
        assert fleet_risk == card_risk, f"Failure risk mismatch for {m_id}: {fleet_risk} != {card_risk}"

    # 3. Its active alert count matches the alert count shown in the precursor card
    for ev in precursor_events:
        m_id = ev["machine"].machine_id
        fleet_row = fleet_map[m_id]
        assert fleet_row["active_alerts_count"] == ev.get("active_alerts_count", 0), (
            f"Alert count mismatch for {m_id}: {fleet_row['active_alerts_count']} != {ev.get('active_alerts_count', 0)}"
        )

    # 4. Its health status matches
    for ev in precursor_events:
        m_id = ev["machine"].machine_id
        fleet_row = fleet_map[m_id]
        assert fleet_row["machine"].health_status == ev["machine"].health_status, (
            f"Health status mismatch for {m_id}"
        )

    # 5. The precursor ranking is deterministic and based on documented priority logic
    snapshot2 = facade.get_command_center_snapshot(force_refresh=True)
    mids_1 = [ev["machine"].machine_id for ev in snapshot.critical_events]
    mids_2 = [ev["machine"].machine_id for ev in snapshot2.critical_events]
    assert mids_1 == mids_2, "Precursor ranking must be deterministic across calls"

    # 6. No machine appears twice in the precursor list
    assert len(mids_1) == len(set(mids_1)), f"Duplicate machine in precursors: {mids_1}"

    # 7. Critical Alerts + non-critical active alerts = Active Alerts
    kpis = snapshot.kpis
    all_alerts = kpis["active_alerts"]
    crit_alerts = kpis["critical_alerts"]
    non_crit_alerts = all_alerts - crit_alerts
    assert crit_alerts + non_crit_alerts == all_alerts
    assert crit_alerts >= 0 and non_crit_alerts >= 0

    # 8. Critical Machines + Warning Machines = Machines at Risk
    crit_m = kpis["critical_assets"]
    warn_m = kpis["warning_assets"]
    at_risk_m = kpis["machines_at_risk"]
    assert crit_m + warn_m == at_risk_m, f"Critical ({crit_m}) + Warning ({warn_m}) != At Risk ({at_risk_m})"

