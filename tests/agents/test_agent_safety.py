"""Tests verifying agent safety boundaries and operational action containment.

Strict adherence to AGENT.md:
- Agent CANNOT directly execute work orders
- Agent CANNOT bypass the ActionPolicyEngine
- Critical maintenance actions always require human sign-off
- Repository state has 0 work orders created by the agent alone
"""

from datetime import datetime, timezone
import pytest

from domain.enums import FailureMode, Severity
from domain.models import Action, Alert, Machine
from repositories.memory.memory_repository import InMemoryRepository
from services.policy_service import ActionPolicyEngine
from agents.reliability.agent import ReliabilityInvestigationAgent


def test_agent_never_creates_work_order_directly():
    repo = InMemoryRepository()
    agent = ReliabilityInvestigationAgent(repository=repo)

    # Trigger alert
    alert = Alert(
        alert_id="ALT-M204-SAFETY",
        machine_id="M204",
        severity=Severity.CRITICAL,
        trigger_reason="Emergency critical risk",
        risk_score=0.92,
        failure_mode=FailureMode.BEARING_DEGRADATION,
    )
    repo.create_alert(alert)

    # Run investigation
    res = agent.investigate_alert("ALT-M204-SAFETY")

    # Verify that an Approval is requested
    assert res.action_proposal.requires_approval is True
    assert res.approval is not None
    assert res.approval.status.value == "PENDING"

    # CRITICAL: Verify NO work orders were added to the repository!
    work_orders = repo.list_work_orders(machine_id="M204")
    assert len(work_orders) == 0


def test_policy_engine_mandates_approval_for_critical_assets():
    policy = ActionPolicyEngine()
    critical_mach = Machine(
        machine_id="M204",
        machine_code="M204",
        name="M204 Conveyor Motor",
        line_id="LINE-B",
        criticality="CRITICAL",
    )

    action = Action(
        action_id="ACT-01",
        recommendation_id="REC-01",
        action_type="CREATE_WORK_ORDER",
        payload={"machine_id": "M204"},
        requires_approval=True,
    )

    assert policy.requires_approval(action, critical_mach) is True
