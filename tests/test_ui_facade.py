"""Tests for CommandCenterFacade and Streamlit UI Service Layer.

Follows Phase 12-14 validation requirements:
- Verifies facade queries return typed deterministic data
- Verifies full operational lifecycle through the facade
- Verifies human approval enforcement and work order creation
- Verifies physical verification and failure recovery paths
"""

from __future__ import annotations

import pytest

from app.streamlit.services.view_service import CommandCenterFacade
from domain.enums import (
    AlertStatus,
    ApprovalStatus,
    HealthStatus,
    InvestigationStatus,
    VerificationStatus,
    WorkOrderStatus,
)


@pytest.fixture
def facade() -> CommandCenterFacade:
    """Return a fresh facade instance with seeded in-memory store."""
    f = CommandCenterFacade(backend_mode="in_memory")
    f.reset_demo()
    return f


def test_facade_kpis(facade: CommandCenterFacade) -> None:
    """Verify fleet KPIs are computed deterministically."""
    kpis = facade.get_kpis()
    assert "oee" in kpis
    assert "availability" in kpis
    assert "performance" in kpis
    assert "quality" in kpis
    assert kpis["total_machines"] >= 5
    assert kpis["critical_assets"] >= 1  # M204 is degraded in initial state
    assert kpis["active_alerts"] >= 1


def test_facade_critical_events(facade: CommandCenterFacade) -> None:
    """Verify critical events list contains M204 alert with context."""
    events = facade.get_critical_events()
    assert len(events) >= 1
    m204_ev = next((e for e in events if e["machine"].machine_id == "M204"), None)
    assert m204_ev is not None
    assert m204_ev["alert"].status == AlertStatus.OPEN
    assert m204_ev["risk"] is not None
    assert m204_ev["risk"].risk_score > 0.50
    assert m204_ev["features"] is not None
    assert m204_ev["oee"] is not None


def test_facade_asset_grid_and_detail(facade: CommandCenterFacade) -> None:
    """Verify asset grid and machine detail methods."""
    grid = facade.get_asset_grid()
    assert len(grid) >= 5
    # M204 should be near top due to critical/degraded status
    assert grid[0]["machine"].machine_id == "M204"

    detail = facade.get_asset_detail("M204")
    assert detail is not None
    assert detail["machine"].machine_id == "M204"
    assert len(detail["components"]) >= 3
    assert len(detail["sensors"]) >= 3
    assert detail["risk"] is not None
    assert detail["oee"] is not None


def test_facade_telemetry_history(facade: CommandCenterFacade) -> None:
    """Verify raw telemetry history extraction for Plotly charting."""
    hist = facade.get_telemetry_history("M204", limit=40)
    assert len(hist["vibration_measurements"]) > 0
    assert len(hist["temperature_measurements"]) > 0
    assert hist["vibration_baseline"] is not None
    assert hist["temperature_baseline"] is not None


def test_facade_deterministic_search(facade: CommandCenterFacade) -> None:
    """Verify search across machines, alerts, and work orders."""
    res_m = facade.search_entities("M204")
    assert len(res_m) >= 1
    assert any(r["id"] == "M204" for r in res_m)

    res_conveyor = facade.search_entities("conveyor")
    assert len(res_conveyor) >= 1

    res_empty = facade.search_entities("")
    assert res_empty == []


def test_facade_closed_loop_workflow(facade: CommandCenterFacade) -> None:
    """Verify complete operational lifecycle executed via facade."""
    # 1. Alert exists
    alerts = facade.repo.list_alerts(machine_id="M204", status=AlertStatus.OPEN)
    assert len(alerts) >= 1
    alert = alerts[0]

    # 2. Run Investigation via Canonical InvestigationService
    inv_res = facade.run_reliability_investigation(alert.alert_id)
    assert inv_res.status == InvestigationStatus.COMPLETED
    assert inv_res.finding is not None
    assert inv_res.recommendation is not None
    assert inv_res.approval is None  # M5 Boundary: strictly advisory, zero auto-approval

    inv_id = inv_res.investigation_id
    app_id = f"APP-{inv_id}"

    # Governance Boundary: human operator requests approval for operational action
    from domain.models import Approval
    facade.approval_service.request_approval(
        Approval(
            approval_id=app_id,
            action_id=f"ACT-{inv_id}",
            investigation_id=inv_id,
            machine_id="M204",
            status=ApprovalStatus.PENDING,
            requested_by="lead.technician.dave",
        )
    )

    # 3. Approve Action
    approved = facade.approve_action(
        approval_id=app_id,
        approver_id="lead.technician.dave",
        reason="Approved emergency SKF bearing replacement.",
    )
    assert approved.status == ApprovalStatus.APPROVED

    # 4. Create Work Order from Approval
    wo = facade.create_work_order_from_approval(
        approval_id=app_id,
        caller_actor="lead.technician.dave",
    )
    assert wo.status == WorkOrderStatus.APPROVED
    assert wo.machine_id == "M204"

    # 5. Start Work Order
    started_wo = facade.start_work_order(wo.work_order_id, technician_name="tech.mike")
    assert started_wo.status == WorkOrderStatus.IN_PROGRESS

    # 6. Complete Work Order
    completed_wo, maint_event = facade.complete_work_order(
        work_order_id=wo.work_order_id,
        technician_name="tech.mike",
        duration_hours=2.5,
        notes="Replaced DE bearing with SKF 6205-2RSH. Greased with Polyrex EM.",
        actions_performed=["LOTO", "decouple", "bearing_swap", "alignment"],
    )
    assert completed_wo.status == WorkOrderStatus.COMPLETED
    assert maint_event is not None
    assert maint_event.work_order_id == wo.work_order_id

    # 7. Physical Verification (Nominal Recovery)
    verif = facade.run_verification(
        work_order_id=wo.work_order_id,
        verifier="reliability.engineer.elena",
        simulate_failure=False,
    )
    assert verif.verification_status == VerificationStatus.VERIFIED
    assert verif.is_recovered is True
    assert verif.post_vibration_rms < 0.50
    assert verif.post_risk_score < 0.25

    # 8. Verify Machine Health Restored
    m204 = facade.repo.get_machine("M204")
    assert m204.health_status == HealthStatus.HEALTHY


def test_facade_failed_verification_workflow(facade: CommandCenterFacade) -> None:
    """Verify failed physical verification leaves machine in degraded state."""
    # 1. Investigate & Approve
    alerts = facade.repo.list_alerts(machine_id="M204", status=AlertStatus.OPEN)
    alert = alerts[0]
    inv_res = facade.run_reliability_investigation(alert.alert_id)
    assert inv_res.status == InvestigationStatus.COMPLETED
    assert inv_res.approval is None  # M5 boundary
    app_id = f"APP-{inv_res.investigation_id}"

    from domain.models import Approval
    facade.approval_service.request_approval(
        Approval(
            approval_id=app_id,
            action_id=f"ACT-{inv_res.investigation_id}",
            investigation_id=inv_res.investigation_id,
            machine_id="M204",
            status=ApprovalStatus.PENDING,
            requested_by="lead.dave",
        )
    )

    facade.approve_action(app_id, "lead.dave", "Approved.")
    wo = facade.create_work_order_from_approval(app_id, "lead.dave")
    facade.start_work_order(wo.work_order_id, "tech.mike")
    facade.complete_work_order(
        work_order_id=wo.work_order_id,
        technician_name="tech.mike",
        duration_hours=1.0,
        notes="Attempted quick grease without bearing replacement.",
        actions_performed=["grease_repack"],
    )

    # 2. Verify with simulate_failure=True
    verif = facade.run_verification(
        work_order_id=wo.work_order_id,
        verifier="eng.elena",
        simulate_failure=True,
    )
    assert verif.verification_status in (VerificationStatus.FAILED, VerificationStatus.PARTIALLY_VERIFIED)
    assert verif.is_recovered is False

    # Machine must remain degraded
    m204 = facade.repo.get_machine("M204")
    assert m204.health_status != HealthStatus.HEALTHY


def test_streamlit_app_renders_and_navigates_all_views() -> None:
    """Verify Streamlit application initializes, renders, and navigates across all views."""
    from pathlib import Path
    from streamlit.testing.v1 import AppTest

    script_path = str(Path(__file__).resolve().parent.parent / "app" / "streamlit_app.py")
    at = AppTest.from_file(script_path)
    at.run(timeout=10)
    assert len(at.exception) == 0, f"App execution failed: {at.exception}"
    assert len(at.markdown) > 0

    views = [
        "Command Center",
        "Assets",
        "Reliability",
        "OEE",
        "Quality",
        "Maintenance",
        "Work Orders",
        "AI Investigations",
        "Knowledge",
        "Agent Activity",
        "Data & Pipelines",
        "Settings",
    ]
    for view_name in views:
        at.session_state["active_nav"] = view_name
        at.run(timeout=10)
        assert len(at.exception) == 0, f"Exception rendering view {view_name}: {at.exception}"
        assert len(at.markdown) > 0, f"View {view_name} rendered 0 markdown elements"


def test_streamlit_app_rerun_resilience() -> None:
    """Verify script re-execution does not yield an empty/black screen on subsequent reruns."""
    from pathlib import Path
    from streamlit.testing.v1 import AppTest

    script_path = str(Path(__file__).resolve().parent.parent / "app" / "streamlit_app.py")
    at = AppTest.from_file(script_path)
    at.run()
    initial_elements = len(at.markdown)
    assert initial_elements > 0

    # Simulate subsequent user interactions and reruns
    at.run()
    assert len(at.markdown) == initial_elements
    assert len(at.exception) == 0

    at.run()
    assert len(at.markdown) == initial_elements
    assert len(at.exception) == 0


def test_streamlit_app_snowflake_unavailable_guardrail(monkeypatch) -> None:
    """Verify Snowflake unconfigured state displays explicit error banner without hanging."""
    from pathlib import Path
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "")
    monkeypatch.setenv("SNOWFLAKE_USER", "")
    monkeypatch.setenv("SNOWFLAKE_PASSWORD", "")

    script_path = str(Path(__file__).resolve().parent.parent / "app" / "streamlit_app.py")
    at = AppTest.from_file(script_path)
    at.session_state["backend_mode"] = "snowflake"
    at.run(timeout=10)

    assert len(at.exception) == 0
    assert any("STORAGE BACKEND UNAVAILABLE" in m.value for m in at.markdown)


