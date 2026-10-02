"""Tests for CommandCenterFacade Canonical Investigation Migration (M6.5.5.1).

Validates:
1. CommandCenterFacade uses InvestigationService and M4InvestigationToolRegistry.
2. Production facade has zero dependency on legacy ReliabilityInvestigationAgent.
3. run_reliability_investigation() returns canonical InvestigationResult.
4. Strict M5 Boundary: investigations are advisory-only, zero ACTION_* / Approval / Work Order records.
5. Strict Backend Selection: Snowflake configuration failure raises RepositoryUnavailableError (no silent fallback).
6. Persisted investigation loading through facade remains fully functional.
7. Agent activity tool calls are sourced from M4 tool registry.
"""

from __future__ import annotations

import pytest

from app.streamlit.services.view_service import CommandCenterFacade
from domain.enums import AlertStatus, InvestigationStatus, TriggerType
from domain.exceptions import RepositoryUnavailableError
from domain.models import (
    Approval,
    Evidence,
    Finding,
    Hypothesis,
    Investigation,
    InvestigationRequest,
    InvestigationResult,
    Recommendation,
)
from services.investigation_service import InvestigationService
from tools.registry import M4InvestigationToolRegistry


@pytest.fixture
def facade() -> CommandCenterFacade:
    """Return fresh in-memory CommandCenterFacade."""
    f = CommandCenterFacade(backend_mode="in_memory")
    f.reset_demo()
    return f


def test_facade_wires_canonical_investigation_service(facade: CommandCenterFacade) -> None:
    """Verify CommandCenterFacade instantiates canonical InvestigationService and M4 registry."""
    assert hasattr(facade, "investigation_service")
    assert isinstance(facade.investigation_service, InvestigationService)
    assert hasattr(facade, "tool_registry")
    assert isinstance(facade.tool_registry, M4InvestigationToolRegistry)
    assert not hasattr(facade, "agent"), "Legacy ReliabilityInvestigationAgent must not exist on facade"


def test_run_reliability_investigation_returns_canonical_result(facade: CommandCenterFacade) -> None:
    """Verify run_reliability_investigation returns canonical InvestigationResult with advisory recommendation."""
    alerts = facade.repo.list_alerts(machine_id="M204", status=AlertStatus.OPEN)
    assert len(alerts) >= 1
    alert = alerts[0]

    res = facade.run_reliability_investigation(alert.alert_id)
    assert isinstance(res, InvestigationResult)
    assert res.status == InvestigationStatus.COMPLETED
    assert res.machine_id == "M204"
    assert res.investigation_id.startswith("INV-M204-")
    assert len(res.findings) >= 1
    assert len(res.recommendations) >= 1
    assert res.finding is not None
    assert res.recommendation is not None
    assert res.recommendation.status == "ADVISORY"
    assert res.approval is None


def test_investigation_strict_m5_boundary_zero_action_or_approval_mutations(facade: CommandCenterFacade) -> None:
    """Verify investigation execution creates zero approvals, proposals, or work orders."""
    alerts = facade.repo.list_alerts(machine_id="M204", status=AlertStatus.OPEN)
    assert len(alerts) >= 1
    alert = alerts[0]

    approvals_before = len(facade.repo.list_approvals())
    work_orders_before = len(facade.repo.list_work_orders(machine_id="M204"))

    res = facade.run_reliability_investigation(alert.alert_id)

    approvals_after = len(facade.repo.list_approvals())
    work_orders_after = len(facade.repo.list_work_orders(machine_id="M204"))

    assert approvals_after == approvals_before, "Investigation must not create approval records"
    assert work_orders_after == work_orders_before, "Investigation must not create work order records"
    assert res.approval is None, "InvestigationResult.approval must be None (M5 boundary invariant)"


def test_facade_snowflake_unavailable_strict_error_no_silent_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify Snowflake unconfigured or unavailable state raises RepositoryUnavailableError."""
    monkeypatch.setenv("STORAGE_BACKEND", "snowflake")
    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "")
    monkeypatch.setenv("SNOWFLAKE_USER", "")
    monkeypatch.setenv("SNOWFLAKE_PASSWORD", "")

    with pytest.raises(RepositoryUnavailableError) as exc_info:
        CommandCenterFacade(backend_mode="snowflake")

    assert "Snowflake backend requested" in str(exc_info.value)


def test_facade_persisted_investigation_loading(facade: CommandCenterFacade) -> None:
    """Verify get_investigations() and get_investigation_detail() load canonical investigations."""
    alerts = facade.repo.list_alerts(machine_id="M204", status=AlertStatus.OPEN)
    alert = alerts[0]

    res = facade.run_reliability_investigation(alert.alert_id)
    inv_id = res.investigation_id

    # List investigations
    invs = facade.get_investigations()
    assert any(i.investigation_id == inv_id for i in invs)

    # Detail loading
    detail = facade.get_investigation_detail(inv_id)
    assert detail is not None
    assert detail["investigation"].investigation_id == inv_id
    assert detail["investigation"].status == InvestigationStatus.COMPLETED
    assert len(detail["evidence"]) > 0
    assert len(detail["hypotheses"]) > 0
    assert detail["finding"] is not None
    assert detail["recommendation"] is not None
    assert detail["recommendation"].status == "ADVISORY"
    assert detail["approval"] is None


def test_facade_get_agent_activity_uses_m4_tool_registry(facade: CommandCenterFacade) -> None:
    """Verify get_agent_activity() aggregates tool executions from M4 tool registry."""
    alerts = facade.repo.list_alerts(machine_id="M204", status=AlertStatus.OPEN)
    facade.run_reliability_investigation(alerts[0].alert_id)

    activity = facade.get_agent_activity()
    assert "tool_calls" in activity
    assert len(activity["tool_calls"]) > 0
    tool_names = {tc.tool_name for tc in activity["tool_calls"]}
    # M4 governed tools executed during investigation
    assert any("telemetry" in tn or "sensor" in tn or "asset" in tn or "machine" in tn for tn in tool_names)


def test_investigation_result_backward_compatibility_properties() -> None:
    """Verify InvestigationResult convenience properties maintain interface compatibility."""
    f = Finding(finding_id="F-1", investigation_id="INV-1", summary="Finding 1")
    r = Recommendation(recommendation_id="R-1", investigation_id="INV-1", title="Rec 1", status="ADVISORY")
    res = InvestigationResult(
        investigation_id="INV-1",
        machine_id="M204",
        summary="Summary test",
        findings=[f],
        recommendations=[r],
        evidence_refs=["EV-1"],
    )

    assert res.finding == f
    assert res.recommendation == r
    assert res.investigation.investigation_id == "INV-1"
    assert res.approval is None
