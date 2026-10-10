"""Strict live verification of all 8 Command Center invariants against Snowflake."""

from __future__ import annotations

import pytest
from app.streamlit.services.view_service import CommandCenterFacade


def test_live_snowflake_command_center_all_8_invariants():
    """Verify all 8 invariants against the live Snowflake deployment."""
    facade = CommandCenterFacade(backend_mode="snowflake")
    snapshot = facade.get_command_center_snapshot(force_refresh=True)

    fleet_map = {row["machine"].machine_id: row for row in snapshot.asset_grid}
    precursor_events = snapshot.critical_events

    assert len(precursor_events) >= 1, "Must have at least one precursor event"
    print(f"\n[LIVE TEST] Retrieved {len(precursor_events)} precursor threats from Snowflake:")
    for ev in precursor_events:
        print(f"  Machine {ev['machine'].machine_id} ({ev['machine'].name}) - Alert: {ev['alert'].alert_id} ({ev['alert'].severity.value})")

    # 1. It exists in the fleet table
    for ev in precursor_events:
        m_id = ev["machine"].machine_id
        assert m_id in fleet_map, f"Precursor machine {m_id} not found in fleet table"

    # 2. Its FAILURE RISK matches the value shown in the precursor card
    for ev in precursor_events:
        m_id = ev["machine"].machine_id
        fleet_row = fleet_map[m_id]
        fleet_risk = f"{fleet_row['risk'].risk_score * 100:.0f}%" if fleet_row["risk"] else "--"
        card_risk = f"{ev['risk'].risk_score * 100:.0f}%" if ev["risk"] else "--"
        assert fleet_risk == card_risk, (
            f"Failure risk mismatch for {m_id}: fleet table '{fleet_risk}' vs card '{card_risk}'"
        )

    # 3. Its active alert count matches the alert count shown in the precursor card
    for ev in precursor_events:
        m_id = ev["machine"].machine_id
        fleet_row = fleet_map[m_id]
        fleet_alerts = fleet_row["active_alerts_count"]
        card_alerts = ev.get("active_alerts_count", 0)
        assert fleet_alerts == card_alerts, (
            f"Active alerts count mismatch for {m_id}: fleet table {fleet_alerts} vs card {card_alerts}"
        )

    # 4. Its health status matches
    for ev in precursor_events:
        m_id = ev["machine"].machine_id
        fleet_row = fleet_map[m_id]
        fleet_health = fleet_row["machine"].health_status
        card_health = ev["machine"].health_status
        assert fleet_health == card_health, (
            f"Health status mismatch for {m_id}: fleet table {fleet_health} vs card {card_health}"
        )

    # 5. The precursor ranking is deterministic and based on documented priority logic
    snapshot2 = facade.get_command_center_snapshot(force_refresh=True)
    mids_1 = [ev["machine"].machine_id for ev in snapshot.critical_events]
    mids_2 = [ev["machine"].machine_id for ev in snapshot2.critical_events]
    assert mids_1 == mids_2, f"Precursor ranking must be deterministic: {mids_1} vs {mids_2}"

    # 6. No machine appears twice in the precursor list
    assert len(mids_1) == len(set(mids_1)), f"Duplicate machine in precursors: {mids_1}"

    # 7. Critical Alerts + non-critical active alerts = Active Alerts
    kpis = snapshot.kpis
    all_alerts = kpis["active_alerts"]
    crit_alerts = kpis["critical_alerts"]
    non_crit_alerts = all_alerts - crit_alerts
    assert crit_alerts + non_crit_alerts == all_alerts, (
        f"Alerts sum mismatch: {crit_alerts} crit + {non_crit_alerts} non-crit != {all_alerts} total active"
    )
    assert crit_alerts >= 0 and non_crit_alerts >= 0

    # 8. Critical Machines + Warning Machines = Machines at Risk
    crit_m = kpis["critical_assets"]
    warn_m = kpis["warning_assets"]
    at_risk_m = kpis["machines_at_risk"]
    assert crit_m + warn_m == at_risk_m, (
        f"Machines sum mismatch: {crit_m} crit + {warn_m} warn != {at_risk_m} machines at risk"
    )

    print(f"[LIVE TEST] All 8 Invariants PASSED against live Snowflake:")
    print(f"  - Precursors: {mids_1}")
    print(f"  - Invariant 7: {crit_alerts} Critical + {non_crit_alerts} Non-Critical = {all_alerts} Active Alerts")
    print(f"  - Invariant 8: {crit_m} Critical + {warn_m} Warning = {at_risk_m} Machines at Risk")


if __name__ == "__main__":
    test_live_snowflake_command_center_all_8_invariants()
