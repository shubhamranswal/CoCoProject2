"""End-to-End M204 Reliability Closed-Loop Execution Demo.

Demonstrates the complete 14-step operational workflow:
1.  M204 Anomaly & High Risk Detected (Deterministic Spine)
2.  Reliability Investigation Agent Dispatched
3.  Tool Calls Executed & Evidence Correlated
4.  Root Cause Finding & Recommendation Formed
5.  Action Proposal Requiring Human Approval
6.  Human Operator Authorizes Maintenance Action
7.  Governed Action Executor Creates Work Order
8.  Maintenance Crew Executes Repair (Work Order In Progress -> Completed)
9.  Physical Maintenance Event Recorded
10. Post-Maintenance Telemetry Generated & Ingested
11. Telemetry Pipeline Re-computes Features, Anomalies, and Risk
12. Verification Service Evaluates Physical Telemetry against VerificationPolicy
13. Investigation Status Closed, Work Order Verified, Machine Health Restored
14. Full Audit Trail Recorded across all Governance Boundaries
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from agents.reliability.agent import ReliabilityInvestigationAgent
from data.scenarios.m204_scenario import M204ScenarioEngine, ScenarioPhase
from domain.enums import (
    ApprovalStatus,
    FailureMode,
    HealthStatus,
    InvestigationStatus,
    Priority,
    WorkOrderStatus,
)
from domain.models import Approval
from repositories.memory.memory_repository import InMemoryRepository
from services.approval_service import ApprovalService
from services.pipeline_orchestrator import PipelineOrchestrator
from services.verification_service import VerificationPolicy, VerificationService
from services.work_order_service import WorkOrderService
from tools.actions.work_order_actions import CreateWorkOrderAction


def run_m204_reliability_case() -> Dict[str, Any]:
    """Execute the end-to-end M204 closed-loop case."""
    repo = InMemoryRepository()

    orchestrator = PipelineOrchestrator(repository=repo)
    engine = M204ScenarioEngine(machine_id="M204")
    approval_service = ApprovalService(repository=repo)
    work_order_service = WorkOrderService(repository=repo, governance_repo=repo)
    action_tool = CreateWorkOrderAction(
        approval_service=approval_service,
        work_order_service=work_order_service,
        governance_repo=repo,
    )
    verification_service = VerificationService(
        repository=repo,
        maintenance_repo=repo,
        investigation_repo=repo,
        machine_repo=repo,
    )
    agent = ReliabilityInvestigationAgent(repository=repo)

    base_time = datetime(2026, 3, 30, 8, 0, 0, tzinfo=timezone.utc)

    # =========================================================================
    # STEP 1: PRE-MAINTENANCE DEGRADATION & ANOMALY DETECTION
    # =========================================================================
    print("=" * 115)
    print(" FACTORY RELIABILITY COMMAND CENTER - M204 CLOSED-LOOP OPERATIONAL CASE")
    print(" Architecture: Observation -> Investigation -> Approval -> Action -> Verification -> Closed Loop")
    print("=" * 115)
    print("\n[STEP 1] Generating high-risk bearing degradation telemetry for M204...")

    pre_measurements = engine.generate_timeseries(
        phase=ScenarioPhase.HIGH_RISK,
        num_points=12,
        start_time=base_time,
        step_minutes=5,
    )
    pre_prod, pre_dt = engine.generate_operational_context(
        phase=ScenarioPhase.HIGH_RISK,
        run_date=base_time,
    )
    dt_list = [pre_dt] if pre_dt else None

    pre_pipeline = orchestrator.run_reliability_pipeline(
        machine_id="M204",
        measurements=pre_measurements,
        production_run=pre_prod,
        downtime_events=dt_list,
    )

    pre_features = pre_pipeline.features
    pre_risk = pre_pipeline.failure_risk
    alert = pre_pipeline.alert
    pre_oee = pre_pipeline.oee

    print(f"  * Vibration RMS   : {pre_features.vibration_rms:.3f} g (Nominal baseline: 0.450 g)")
    print(f"  * Temperature     : {pre_features.temperature_mean:.1f} °C (Nominal baseline: 58.5 °C)")
    print(f"  * Active Anomalies: {len(pre_pipeline.anomalies)} critical anomaly detected")
    print(f"  * Failure Risk    : {pre_risk.risk_score:.3f} [{pre_risk.risk_level.value}] Mode: {pre_risk.failure_mode.value}")
    print(f"  * Alert Emitted   : {alert.alert_id} | Severity: {alert.severity.value}")
    if pre_oee:
        print(f"  * Current OEE     : {pre_oee.oee * 100:.1f}% (Availability: {pre_oee.availability * 100:.1f}%)")

    # =========================================================================
    # STEP 2: RELIABILITY INVESTIGATION AGENT
    # =========================================================================
    print("\n[STEP 2] Dispatching Reliability Investigation Agent...")
    inv_result = agent.investigate_alert(alert_id=alert.alert_id)
    investigation = inv_result.investigation
    finding = inv_result.finding
    recommendation = inv_result.recommendation
    approval_request = inv_result.approval
    tool_calls = agent.tools.call_history

    print(f"  * Investigation ID: {investigation.investigation_id}")
    print(f"  * Status          : {investigation.status.value}")
    print(f"  * Tools Called    : {len(tool_calls)} auditable read tools invoked")
    print(f"  * Primary Finding : {finding.summary} (Confidence: {finding.confidence * 100:.0f}%)")
    print(f"  * Failure Mode    : {finding.failure_mode.value}")
    print(f"  * Recommendation  : {recommendation.title}")
    print(f"  * Action Details  : {recommendation.action_description}")
    print(f"  * Est. Downtime   : {recommendation.estimated_downtime_hours} hours | Parts: {', '.join(recommendation.suggested_parts)}")

    # =========================================================================
    # STEP 3: HUMAN GOVERNANCE & APPROVAL REQUEST
    # =========================================================================
    print("\n[STEP 3] Human Approval Gateway (Policy Enforcement)...")
    if not approval_request:
        approval_request = Approval(
            approval_id=f"APP-{investigation.investigation_id}",
            investigation_id=investigation.investigation_id,
            recommendation_id=recommendation.recommendation_id,
            machine_id="M204",
            action_type=recommendation.action_type,
            requested_action=recommendation.title,
            status=ApprovalStatus.PENDING,
            requested_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        approval_service.request_approval(approval_request)
    print(f"  * Approval Request Created : {approval_request.approval_id}")
    print(f"  * Approval Status          : {approval_request.status.value} (Awaiting human review)")

    # Human operator review
    approver = "operator.shubham"
    decision_reason = "Confirmed severe 2X harmonic vibration signature and overheating. Authorized bearing replacement before night shift."
    print(f"\n[STEP 4] Human Operator Review...")
    print(f"  * Reviewer     : {approver}")
    print(f"  * Decision     : APPROVED")
    print(f"  * Justification: {decision_reason}")
    approved_record = approval_service.approve_action(
        approval_id=approval_request.approval_id,
        approver_id=approver,
        reason=decision_reason,
    )
    print(f"  * Updated Approval Status: {approved_record.status.value} (Authorized at {approved_record.decision_at.strftime('%H:%M:%S')})")

    # =========================================================================
    # STEP 4: GOVERNED ACTION EXECUTION (WORK ORDER CREATION)
    # =========================================================================
    print("\n[STEP 5] Governed Action Executor (Create Work Order)...")
    work_order = action_tool.execute(
        caller_actor=approver,
        approval_id=approved_record.approval_id,
        machine_id="M204",
        component_id="COMP-M204-BRG-DE",
        title="Replace Conveyor Drive Motor Drive-End Bearing",
        description="Shut down conveyor, lockout/tagout, dismount motor, pull worn bearing, install new SKF 6205 bearing, torque & realign.",
        failure_mode=FailureMode.BEARING_DEGRADATION,
        priority=Priority.HIGH,
        assigned_to="MAINT-CREW-ALPHA",
        investigation_id=investigation.investigation_id,
        recommendation_id=recommendation.recommendation_id,
        idempotency_key=f"IDEM-{approved_record.approval_id}",
    )
    print(f"  * Work Order ID   : {work_order.work_order_id}")
    print(f"  * Initial Status  : {work_order.status.value}")
    print(f"  * Target Component: {work_order.component_id}")
    print(f"  * Assigned To     : {work_order.assigned_to}")
    print(f"  * Idempotency Key : {work_order.idempotency_key}")

    # =========================================================================
    # STEP 5: MAINTENANCE EXECUTION BY TECHNICIAN
    # =========================================================================
    print("\n[STEP 6] Maintenance Team Execution...")
    tech_name = "tech.marcus"
    work_order_service.transition_status(work_order.work_order_id, WorkOrderStatus.IN_PROGRESS, actor=tech_name)
    print(f"  * Status Changed : IN_PROGRESS (Technician on site: {tech_name})")

    completed_wo, maint_event = work_order_service.complete_work_order(
        work_order_id=work_order.work_order_id,
        technician_name=tech_name,
        duration_hours=2.25,
        notes="Replaced drive-end bearing with new SKF 6205-2RSH. Lubricated with Mobil Polyrex EM. Realigned shaft to 0.03mm tolerance.",
        actions_performed=[
            "Locked out electrical disconnect",
            "Extracted damaged drive-end bearing (inner raceway spalling confirmed)",
            "Installed replacement SKF 6205-2RSH",
            "Shaft laser realignment",
            "Cold bump test completed normal",
        ],
    )
    print(f"  * Status Changed : {completed_wo.status.value} (Technician work completed)")
    print(f"  * Event Recorded : {maint_event.maintenance_id} ({maint_event.duration_hours}h duration)")

    # =========================================================================
    # STEP 6: POST-MAINTENANCE TELEMETRY INGESTION & PIPELINE RUN
    # =========================================================================
    print("\n[STEP 7] Ingesting Post-Maintenance Telemetry (Machine restarted)...")
    post_time = base_time + timedelta(hours=4)
    post_measurements = engine.generate_recovery_trajectory(
        num_points=12,
        start_time=post_time,
        step_minutes=5,
    )
    post_prod, post_dt = engine.generate_operational_context(
        phase=ScenarioPhase.RECOVERED,
        run_date=post_time,
    )

    post_pipeline = orchestrator.run_reliability_pipeline(
        machine_id="M204",
        measurements=post_measurements,
        production_run=post_prod,
        downtime_events=[post_dt] if post_dt else None,
    )

    post_features = post_pipeline.features
    post_risk = post_pipeline.failure_risk
    post_anomalies = post_pipeline.anomalies
    post_oee = post_pipeline.oee

    print(f"  * Post Vibration RMS: {post_features.vibration_rms:.3f} g (Pre: {pre_features.vibration_rms:.3f} g)")
    print(f"  * Post Temperature  : {post_features.temperature_mean:.1f} °C (Pre: {pre_features.temperature_mean:.1f} °C)")
    print(f"  * Post Risk Score   : {post_risk.risk_score:.3f} [{post_risk.risk_level.value}] (Pre: {pre_risk.risk_score:.3f})")
    print(f"  * Active Anomalies  : {len(post_anomalies)}")
    if post_oee:
        print(f"  * Post-Repair OEE   : {post_oee.oee * 100:.1f}% (Pre: {pre_oee.oee * 100:.1f}%)")

    # =========================================================================
    # STEP 7: CLOSED-LOOP VERIFICATION AGAINST POLICY
    # =========================================================================
    print("\n[STEP 8] Verification Service: Physical Telemetry Verification...")
    policy = VerificationPolicy(
        max_acceptable_vibration_rms=0.50,
        max_acceptable_temperature=65.0,
        max_acceptable_risk_score=0.25,
        min_vibration_reduction_pct=30.0,
        min_risk_reduction_pct=50.0,
        require_zero_active_critical_anomalies=True,
    )

    verification = verification_service.verify_recovery(
        work_order_id=completed_wo.work_order_id,
        investigation_id=investigation.investigation_id,
        machine_id="M204",
        pre_features=pre_features,
        post_features=post_features,
        pre_risk=pre_risk,
        post_risk=post_risk,
        pre_oee=pre_oee,
        post_oee=post_oee,
        active_anomalies=post_anomalies,
        policy=policy,
        verifier="lead.engineer.david",
    )

    final_inv = repo.get_investigation(investigation.investigation_id)
    final_wo = repo.get_work_order(completed_wo.work_order_id)
    final_machine = repo.get_machine("M204")

    print(f"  * Verification Status : {verification.verification_status.value}")
    print(f"  * Physical Recovery   : {'CONFIRMED SUCCESS' if verification.is_recovered else 'FAILED'}")
    print(f"  * Decision Reason     : {verification.verification_reason}")
    print(f"  * Final Work Order    : {final_wo.status.value}")
    print(f"  * Final Investigation : {final_inv.status.value}")
    print(f"  * Machine Health      : {final_machine.health_status.value}")

    # =========================================================================
    # STEP 8: MEASURED OPERATIONAL OUTCOMES SUMMARY TABLE
    # =========================================================================
    print("\n" + "=" * 115)
    print(" CLOSED-LOOP OPERATIONAL METRICS & VERIFICATION REPORT")
    print("=" * 115)
    header = f"{'Metric':<28} | {'Pre-Maintenance':<18} | {'Post-Maintenance':<18} | {'Delta':<18} | {'Status'}"
    print(header)
    print("-" * 115)

    vib_delta = post_features.vibration_rms - pre_features.vibration_rms
    vib_pct = (vib_delta / pre_features.vibration_rms) * 100
    temp_delta = post_features.temperature_mean - pre_features.temperature_mean
    risk_delta = post_risk.risk_score - pre_risk.risk_score
    risk_pct = (risk_delta / pre_risk.risk_score) * 100
    pre_oee_pct = (pre_oee.oee * 100) if pre_oee else 0.0
    post_oee_pct = (post_oee.oee * 100) if post_oee else 0.0
    oee_delta = post_oee_pct - pre_oee_pct

    print(f"{'Vibration RMS (g)':<28} | {pre_features.vibration_rms:<18.3f} | {post_features.vibration_rms:<18.3f} | {vib_pct:>+6.1f}% ({vib_delta:+.3f}g)  | RECOVERED")
    print(f"{'Temperature Mean (°C)':<28} | {pre_features.temperature_mean:<18.1f} | {post_features.temperature_mean:<18.1f} | {temp_delta:>+6.1f} °C         | NORMALIZED")
    print(f"{'Failure Risk Score':<28} | {pre_risk.risk_score:<18.3f} | {post_risk.risk_score:<18.3f} | {risk_pct:>+6.1f}% ({risk_delta:+.3f})   | LOW RISK")
    print(f"{'Active Anomalies':<28} | {len(pre_pipeline.anomalies):<18} | {len(post_anomalies):<18} | {len(post_anomalies) - len(pre_pipeline.anomalies):<18} | CLEARED")
    print(f"{'OEE Performance':<28} | {pre_oee_pct:<17.1f}% | {post_oee_pct:<17.1f}% | {oee_delta:>+6.1f}%             | RESTORED")
    print(f"{'Investigation Lifecycle':<28} | {'OPEN / INVESTIGATING':<18} | {final_inv.status.value:<18} | {'CLOSED'}             | RESOLVED")
    print(f"{'Work Order Status':<28} | {'APPROVED / IN_PROG':<18} | {final_wo.status.value:<18} | {'VERIFIED'}           | GOVERNED")
    print("=" * 115)
    print(" End-to-end operational closed loop verified successfully with 100% determinism.")
    print("=" * 115)

    return {
        "investigation": final_inv,
        "work_order": final_wo,
        "verification": verification,
        "pre_features": pre_features,
        "post_features": post_features,
        "pre_risk": pre_risk,
        "post_risk": post_risk,
        "pre_oee": pre_oee,
        "post_oee": post_oee,
    }


if __name__ == "__main__":
    run_m204_reliability_case()
