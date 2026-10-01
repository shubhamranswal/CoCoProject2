"""End-to-end integration test for ML predictive closed loop with CoCo agent and verification."""

import uuid
from datetime import datetime, timedelta, timezone

from domain.enums import ApprovalStatus, FailureMode, Priority, WorkOrderStatus, VerificationStatus
from domain.models import PredictionOutcome
from repositories.memory.memory_repository import InMemoryRepository
from ml.features.predictive_features import extract_predictive_features
from ml.models.failure_predictor import BearingFailurePredictor
from agents.reliability.coco_agent import CoCoReliabilityAgent
from services.approval_service import ApprovalService
from services.pipeline_orchestrator import PipelineOrchestrator
from services.work_order_service import WorkOrderService
from services.verification_service import VerificationService, VerificationPolicy
from services.lineage_service import LineageService
from tools.actions.work_order_actions import CreateWorkOrderAction
from data.scenarios.m204_scenario import M204ScenarioEngine, ScenarioPhase


def test_predictive_closed_loop_end_to_end():
    # 1. Setup repository, scenario engine, orchestrator
    repo = InMemoryRepository()
    engine = M204ScenarioEngine("M204")
    orchestrator = PipelineOrchestrator(repository=repo)
    base_time = datetime(2026, 3, 30, 8, 0, 0, tzinfo=timezone.utc)

    # 2. Generate precursor telemetry (degraded bearing state)
    degraded_meas = engine.generate_timeseries(phase=ScenarioPhase.HIGH_RISK, num_points=12, start_time=base_time)
    pre_prod, pre_dt = engine.generate_operational_context(phase=ScenarioPhase.HIGH_RISK, run_date=base_time)
    pre_pipe = orchestrator.run_reliability_pipeline(
        machine_id="M204",
        measurements=degraded_meas,
        production_run=pre_prod,
        downtime_events=[pre_dt] if pre_dt else None,
    )

    # 3. Extract 24 predictive features strictly as of current cutoff
    cutoff_time = degraded_meas[-1].timestamp
    features = extract_predictive_features(degraded_meas, as_of=cutoff_time)
    assert len(features) == 24

    # 4. Predict failure probability using BearingFailurePredictor
    predictor = BearingFailurePredictor()
    prediction = predictor.predict("M204", features, horizon_hours=24, as_of=cutoff_time)
    assert prediction.failure_probability >= 0.70
    assert prediction.threshold_exceeded
    repo.save_prediction(prediction)

    # 5. CoCo Reliability Agent investigates predictive warning
    coco_agent = CoCoReliabilityAgent(repo)
    inv_result = coco_agent.investigate_prediction(prediction)

    assert inv_result.investigation is not None
    assert inv_result.finding is not None
    assert inv_result.action_proposal is not None
    assert inv_result.approval is not None
    app = inv_result.approval

    # 6. Governed Human Approval
    approval_svc = ApprovalService(repo)
    approved_rec = approval_svc.approve_action(
        approval_id=app.approval_id,
        approver_id="Chief Reliability Engineer",
        reason="Confirmed high ML failure risk and harmonic vibration signature",
    )
    assert approved_rec.status == ApprovalStatus.APPROVED

    # 7. Work Order Execution via Governed Action Tool
    wo_svc = WorkOrderService(repository=repo, governance_repo=repo)
    action_tool = CreateWorkOrderAction(
        approval_service=approval_svc,
        work_order_service=wo_svc,
        governance_repo=repo,
    )
    wo = action_tool.execute(
        caller_actor="Chief Reliability Engineer",
        approval_id=app.approval_id,
        machine_id="M204",
        component_id="COMP-M204-BRG-DE",
        title="Predictive Bearing Replacement",
        description="Replace worn drive-end bearing identified by CoCo predictive model",
        failure_mode=FailureMode.BEARING_DEGRADATION,
        priority=Priority.HIGH,
    )
    assert wo.status == WorkOrderStatus.APPROVED

    # 8. Maintenance execution -> COMPLETED
    wo_svc.transition_status(wo.work_order_id, WorkOrderStatus.IN_PROGRESS, actor="TECH-01")
    completed_wo, _ = wo_svc.complete_work_order(
        work_order_id=wo.work_order_id,
        technician_name="TECH-01",
        duration_hours=2.0,
        notes="Replaced DE bearing and laser aligned shaft.",
    )
    assert completed_wo.status == WorkOrderStatus.COMPLETED

    # 9. Post-maintenance telemetry generation (healthy state)
    post_time = base_time + timedelta(hours=3)
    post_meas = engine.generate_recovery_trajectory(num_points=12, start_time=post_time)
    post_prod, post_dt = engine.generate_operational_context(phase=ScenarioPhase.RECOVERED, run_date=post_time)
    post_pipe = orchestrator.run_reliability_pipeline(
        machine_id="M204",
        measurements=post_meas,
        production_run=post_prod,
        downtime_events=[post_dt] if post_dt else None,
    )

    # 10. Verification
    ver_svc = VerificationService(
        repository=repo,
        maintenance_repo=repo,
        investigation_repo=repo,
        machine_repo=repo,
    )
    verification = ver_svc.verify_recovery(
        work_order_id=completed_wo.work_order_id,
        investigation_id=inv_result.investigation.investigation_id,
        machine_id="M204",
        pre_features=pre_pipe.features,
        post_features=post_pipe.features,
        pre_risk=pre_pipe.failure_risk,
        post_risk=post_pipe.failure_risk,
        pre_oee=pre_pipe.oee,
        post_oee=post_pipe.oee,
        active_anomalies=post_pipe.anomalies,
        verifier="Chief Reliability Engineer",
    )
    assert verification.is_recovered
    assert verification.verification_status == VerificationStatus.VERIFIED
    assert verification.post_risk_score < verification.pre_risk_score

    # 11. Predictive feedback loop: Close the outcome
    outcome = PredictionOutcome(
        outcome_id=f"OUT-{uuid.uuid4().hex[:8].upper()}",
        prediction_id=prediction.prediction_id,
        machine_id="M204",
        predicted_failure=True,
        actual_failure=True,  # Proactive catch confirmed by physical repair
        prediction_horizon_hours=24,
        lead_time_hours=4.5,
        verification_id=verification.verification_id,
        is_correct=True,
        notes="Bearing replacement completed; post-maintenance vibration RMS returned to nominal baseline.",
    )
    repo.save_prediction_outcome(outcome)

    # 12. Verify Lineage Service captures complete trace
    lineage_svc = LineageService(repo)
    lineage = lineage_svc.trace_lineage("M204", work_order_id=wo.work_order_id)

    assert lineage.machine_id == "M204"
    assert lineage.prediction_id == prediction.prediction_id
    assert lineage.investigation_id == inv_result.investigation.investigation_id
    assert lineage.approval_id == app.approval_id
    assert lineage.work_order_id == wo.work_order_id
    assert lineage.verification_id == verification.verification_id
    assert lineage.outcome_id == outcome.outcome_id
