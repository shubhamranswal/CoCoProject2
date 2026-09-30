"""End-to-end integration tests for the governed closed-loop reliability case.

Follows AGENT.md & architecture/architecture.md:
- Complete vertical slice:
  Observation -> Investigation -> Approval -> Action -> Maintenance -> Post-Telemetry -> Verification -> Closed Loop
- Validates happy path (successful verification and investigation closure)
- Validates failure path (improper maintenance leads to failed verification and keeps investigation open)
"""

from datetime import datetime, timedelta, timezone
import pytest

from data.scenarios.m204_scenario import M204ScenarioEngine, ScenarioPhase
from domain.enums import (
    ApprovalStatus,
    FailureMode,
    HealthStatus,
    InvestigationStatus,
    Priority,
    VerificationStatus,
    WorkOrderStatus,
)
from repositories.memory.memory_repository import InMemoryRepository
from services.approval_service import ApprovalService
from services.demo_case import run_m204_reliability_case
from services.pipeline_orchestrator import PipelineOrchestrator
from services.verification_service import VerificationPolicy, VerificationService
from services.work_order_service import WorkOrderService
from tools.actions.work_order_actions import CreateWorkOrderAction


def test_m204_closed_loop_reliability_case():
    """Verify the full 14-step M204 case executes end-to-end with 100% determinism."""
    result = run_m204_reliability_case()

    assert result["investigation"].status == InvestigationStatus.CLOSED
    assert result["investigation"].closed_at is not None
    assert result["work_order"].status == WorkOrderStatus.VERIFIED
    assert result["verification"].verification_status == VerificationStatus.VERIFIED
    assert result["verification"].is_recovered is True

    # Physical metrics improvement
    assert result["post_features"].vibration_rms < result["pre_features"].vibration_rms
    assert result["post_features"].vibration_rms <= 0.50
    assert result["post_features"].temperature_mean < result["pre_features"].temperature_mean
    assert result["post_risk"].risk_score < 0.20
    assert result["post_oee"].oee > result["pre_oee"].oee


def test_failed_closed_loop_recovery_path():
    """Verify that improper repair correctly fails physical verification and keeps investigation open."""
    repo = InMemoryRepository()
    orchestrator = PipelineOrchestrator(repository=repo)
    engine = M204ScenarioEngine(machine_id="M204")
    approval_svc = ApprovalService(repository=repo)
    wo_svc = WorkOrderService(repository=repo, governance_repo=repo)
    action_tool = CreateWorkOrderAction(
        approval_service=approval_svc,
        work_order_service=wo_svc,
        governance_repo=repo,
    )
    verif_svc = VerificationService(
        repository=repo,
        maintenance_repo=repo,
        investigation_repo=repo,
        machine_repo=repo,
    )

    base_time = datetime(2026, 3, 30, 8, 0, 0, tzinfo=timezone.utc)

    # 1. Pre-maintenance degradation
    pre_meas = engine.generate_timeseries(phase=ScenarioPhase.HIGH_RISK, num_points=12, start_time=base_time)
    pre_prod, pre_dt = engine.generate_operational_context(phase=ScenarioPhase.HIGH_RISK, run_date=base_time)
    pre_pipe = orchestrator.run_reliability_pipeline(
        machine_id="M204",
        measurements=pre_meas,
        production_run=pre_prod,
        downtime_events=[pre_dt] if pre_dt else None,
    )

    # 2. Governed approval and action
    from agents.reliability.agent import ReliabilityInvestigationAgent
    agent = ReliabilityInvestigationAgent(repository=repo)
    inv_res = agent.investigate_alert(alert_id=pre_pipe.alert.alert_id)
    inv = inv_res.investigation

    app = inv_res.approval
    approval_svc.approve_action(app.approval_id, approver_id="operator.sarah", reason="Authorized repair")

    wo = action_tool.execute(
        caller_actor="operator.sarah",
        approval_id=app.approval_id,
        machine_id="M204",
        component_id="COMP-M204-BRG-DE",
        title="Replace bearing",
        description="Replace worn bearing",
        failure_mode=FailureMode.BEARING_DEGRADATION,
        priority=Priority.HIGH,
    )

    # 3. Technician completes repair (incorrectly)
    completed_wo, _ = wo_svc.complete_work_order(
        work_order_id=wo.work_order_id,
        technician_name="tech.apprentice",
        duration_hours=1.5,
        notes="Replaced bearing, but shaft alignment was not checked.",
    )
    assert completed_wo.status == WorkOrderStatus.COMPLETED

    # 4. Ingest failed recovery trajectory (vibration remains ~0.85g)
    post_time = base_time + timedelta(hours=3)
    post_meas = engine.generate_failed_recovery_trajectory(num_points=12, start_time=post_time)
    post_prod, post_dt = engine.generate_operational_context(phase=ScenarioPhase.ANOMALOUS, run_date=post_time)
    post_pipe = orchestrator.run_reliability_pipeline(
        machine_id="M204",
        measurements=post_meas,
        production_run=post_prod,
        downtime_events=[post_dt] if post_dt else None,
    )

    # 5. Verification evaluation
    verification = verif_svc.verify_recovery(
        work_order_id=completed_wo.work_order_id,
        investigation_id=inv.investigation_id,
        machine_id="M204",
        pre_features=pre_pipe.features,
        post_features=post_pipe.features,
        pre_risk=pre_pipe.failure_risk,
        post_risk=post_pipe.failure_risk,
        pre_oee=pre_pipe.oee,
        post_oee=post_pipe.oee,
        active_anomalies=post_pipe.anomalies,
        verifier="quality.inspector",
    )

    # Verification must fail!
    assert verification.verification_status == VerificationStatus.FAILED
    assert verification.is_recovered is False

    # Investigation must NOT be closed; it must be marked as VERIFICATION_FAILED
    updated_inv = repo.get_investigation(inv.investigation_id)
    assert updated_inv.status == InvestigationStatus.VERIFICATION_FAILED
    assert updated_inv.closed_at is None

    # Work order remains COMPLETED, not VERIFIED
    updated_wo = repo.get_work_order(completed_wo.work_order_id)
    assert updated_wo.status == WorkOrderStatus.COMPLETED

    # Machine health is NOT healthy
    machine = repo.get_machine("M204")
    assert machine.health_status != HealthStatus.HEALTHY
