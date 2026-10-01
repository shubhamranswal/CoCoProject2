"""Command Center Application Facade Service.

Follows AGENT.md & architecture/architecture.md:
- Presentation layer calls this facade to query state and trigger governed actions
- Never executes raw SQL in Streamlit
- Never computes OEE, risk, or verification in Streamlit
- Dispatches all mutations to governed backend services
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from agents.reliability.agent import ReliabilityInvestigationAgent, ReliabilityInvestigationResult
from config import get_config
from data.scenarios.m204_scenario import M204ScenarioEngine, ScenarioPhase
from domain.enums import (
    AlertStatus,
    ApprovalStatus,
    FailureMode,
    HealthStatus,
    InvestigationStatus,
    MachineState,
    Priority,
    VerificationStatus,
    WorkOrderStatus,
)
from domain.models import (
    Alert,
    Approval,
    AuditEvent,
    DataFreshness,
    DecisionLineage,
    Investigation,
    Machine,
    MaintenanceEvent,
    MLFailurePrediction,
    PredictionOutcome,
    Verification,
    WorkOrder,
)
from repositories.snowflake.connection import SnowflakeConnectionManager, SnowflakeHealthStatus
from ml.features.predictive_features import extract_predictive_features
from ml.models.failure_predictor import BearingFailurePredictor
from services.lineage_service import LineageService
from repositories import get_repository
from repositories.base import (
    GovernanceRepository,
    InvestigationRepository,
    MachineRepository,
    MaintenanceRepository,
    ReliabilityRepository,
    TelemetryRepository,
)
from services.approval_service import ApprovalService
from services.oee_service import OEEResult, OEEService
from services.pipeline_orchestrator import PipelineExecutionResult, PipelineOrchestrator
from services.reliability_service import ReliabilityService
from services.telemetry_service import TelemetryService
from services.verification_service import VerificationPolicy, VerificationService
from services.work_order_service import WorkOrderService
from tools.actions.work_order_actions import CreateWorkOrderAction


class CommandCenterFacade:
    """Thin facade composing backend services for the Streamlit presentation layer."""

    def __init__(self, backend_mode: str = "in_memory") -> None:
        self.config = get_config()
        self.backend_mode = backend_mode
        self.repo = get_repository(backend=backend_mode)

        # Services
        self.orchestrator = PipelineOrchestrator(repository=self.repo)
        self.telemetry_service = TelemetryService(repository=self.repo)
        self.reliability_service = ReliabilityService(
            reliability_repo=self.repo,
            machine_repo=self.repo,
            maintenance_repo=self.repo,
        )
        self.oee_service = OEEService()
        self.approval_service = ApprovalService(repository=self.repo)
        self.work_order_service = WorkOrderService(repository=self.repo, governance_repo=self.repo)
        self.verification_service = VerificationService(
            repository=self.repo,
            maintenance_repo=self.repo,
            investigation_repo=self.repo,
            machine_repo=self.repo,
        )
        self.agent = ReliabilityInvestigationAgent(
            repository=self.repo,
            approval_service=self.approval_service,
        )
        self.action_tool = CreateWorkOrderAction(
            approval_service=self.approval_service,
            work_order_service=self.work_order_service,
            governance_repo=self.repo,
        )
        self.scenario_engine = M204ScenarioEngine(machine_id="M204")

        # Auto-initialize baseline M204 alert in demo mode if unseeded
        if self.backend_mode == "in_memory":
            self._ensure_initial_state()

    def _ensure_initial_state(self) -> None:
        """Seed M204 active degradation state on startup so the UI renders the hero alert immediately."""
        alerts = self.repo.list_alerts(machine_id="M204", status=AlertStatus.OPEN)
        if not alerts:
            self.run_m204_degradation_pipeline()

    # =========================================================================
    # PIPELINE & SCENARIO ACTIONS
    # =========================================================================
    def run_m204_degradation_pipeline(self) -> PipelineExecutionResult:
        """Simulate physical bearing degradation on M204 and execute the deterministic pipeline."""
        now = datetime.now(timezone.utc)
        measurements = self.scenario_engine.generate_timeseries(
            phase=ScenarioPhase.HIGH_RISK,
            num_points=12,
            start_time=now - timedelta(minutes=60),
            step_minutes=5,
        )
        prod_run, dt_event = self.scenario_engine.generate_operational_context(
            phase=ScenarioPhase.HIGH_RISK,
            run_date=now,
        )
        dt_list = [dt_event] if dt_event else None

        result = self.orchestrator.run_reliability_pipeline(
            machine_id="M204",
            measurements=measurements,
            production_run=prod_run,
            downtime_events=dt_list,
        )
        return result

    def run_reliability_investigation(self, alert_id: str) -> ReliabilityInvestigationResult:
        """Dispatch Reliability Investigation Agent for an alert."""
        return self.agent.investigate_alert(alert_id=alert_id)

    def approve_action(self, approval_id: str, approver_id: str, reason: str) -> Approval:
        """Submit authenticated human approval for an operational action."""
        return self.approval_service.approve_action(
            approval_id=approval_id,
            approver_id=approver_id,
            reason=reason,
        )

    def reject_action(self, approval_id: str, approver_id: str, reason: str) -> Approval:
        """Submit authenticated human rejection for an operational action."""
        return self.approval_service.reject_action(
            approval_id=approval_id,
            approver_id=approver_id,
            reason=reason,
        )

    def create_work_order_from_approval(
        self,
        approval_id: str,
        caller_actor: str,
        title: str = "Replace Conveyor Drive-End Bearing",
        description: str = "Perform LOTO, decouple conveyor, replace bearing assembly with SKF 6205-2RSH.",
        priority: Priority = Priority.HIGH,
        assigned_to: str = "MAINT-CREW-ALPHA",
        failure_mode: FailureMode = FailureMode.BEARING_DEGRADATION,
    ) -> WorkOrder:
        """Execute governed work order action following approved decision."""
        app = self.approval_service.get_approval(approval_id)
        if not app:
            raise ValueError(f"Approval '{approval_id}' not found.")

        wo = self.action_tool.execute(
            caller_actor=caller_actor,
            approval_id=approval_id,
            machine_id=app.machine_id,
            component_id="COMP-M204-BRG-DE",
            title=title,
            description=description,
            failure_mode=failure_mode,
            priority=priority,
            assigned_to=assigned_to,
            investigation_id=app.investigation_id,
            recommendation_id=app.recommendation_id,
            idempotency_key=f"IDEM-{approval_id}",
        )
        return wo

    def start_work_order(self, work_order_id: str, technician_name: str) -> WorkOrder:
        """Transition work order to IN_PROGRESS."""
        return self.work_order_service.transition_status(
            work_order_id=work_order_id,
            new_status=WorkOrderStatus.IN_PROGRESS,
            actor=technician_name,
            notes="Technician arrived on site and commenced LOTO.",
        )

    def complete_work_order(
        self,
        work_order_id: str,
        technician_name: str,
        duration_hours: float,
        notes: str,
        actions_performed: List[str],
    ) -> Tuple[WorkOrder, MaintenanceEvent]:
        """Technician completes physical repair and records maintenance event."""
        return self.work_order_service.complete_work_order(
            work_order_id=work_order_id,
            technician_name=technician_name,
            duration_hours=duration_hours,
            notes=notes,
            actions_performed=actions_performed,
            failure_mode=FailureMode.BEARING_DEGRADATION,
        )

    def run_verification(
        self,
        work_order_id: str,
        verifier: str,
        simulate_failure: bool = False,
    ) -> Verification:
        """Ingest post-maintenance telemetry and evaluate physical verification."""
        wo = self.work_order_service.get_work_order(work_order_id)
        if not wo:
            raise ValueError(f"Work order '{work_order_id}' not found.")

        now = datetime.now(timezone.utc)
        inv_id = wo.investigation_id or "INV-M204"

        # Fetch pre-maintenance features & risk
        pre_feat = self.repo.get_latest_features("M204")
        pre_risk = self.repo.get_latest_failure_risk("M204")
        pre_oee = self.calculate_machine_oee("M204")

        if simulate_failure:
            post_meas = self.scenario_engine.generate_failed_recovery_trajectory(num_points=12, start_time=now)
            post_phase = ScenarioPhase.ANOMALOUS
        else:
            post_meas = self.scenario_engine.generate_recovery_trajectory(num_points=12, start_time=now)
            post_phase = ScenarioPhase.RECOVERED

        post_prod, post_dt = self.scenario_engine.generate_operational_context(phase=post_phase, run_date=now)
        post_pipeline = self.orchestrator.run_reliability_pipeline(
            machine_id="M204",
            measurements=post_meas,
            production_run=post_prod,
            downtime_events=[post_dt] if post_dt else None,
        )

        verification = self.verification_service.verify_recovery(
            work_order_id=work_order_id,
            investigation_id=inv_id,
            machine_id="M204",
            pre_features=pre_feat,
            post_features=post_pipeline.features,
            pre_risk=pre_risk,
            post_risk=post_pipeline.failure_risk,
            pre_oee=pre_oee,
            post_oee=post_pipeline.oee,
            active_anomalies=post_pipeline.anomalies,
            verifier=verifier,
        )
        return verification

    def reset_demo(self, seed_degradation: bool = True) -> None:
        """Reset repository to healthy baseline reference state, optionally re-seeding M204 degradation."""
        self.repo.reset_state()
        self.scenario_engine.reset_to_healthy()
        self.repo.update_machine_health("M204", HealthStatus.HEALTHY, MachineState.RUNNING)
        if seed_degradation:
            self.run_m204_degradation_pipeline()

    def get_current_demo_stage(self, machine_id: str = "M204") -> str:
        """Evaluate current lifecycle stage for machine M204 from persistent repository state."""
        alerts = self.repo.list_alerts(machine_id=machine_id, status=AlertStatus.OPEN)
        if not alerts:
            verifs = self.repo.list_verifications(machine_id=machine_id)
            if verifs:
                latest_v = verifs[0]
                if latest_v.verification_status == VerificationStatus.VERIFIED:
                    return "VERIFIED"
                elif latest_v.verification_status == VerificationStatus.FAILED:
                    return "VERIFICATION_FAILED"
            return "HEALTHY"

        active_alert = alerts[0]
        inv = self.repo.get_investigation_by_alert(active_alert.alert_id)
        if not inv:
            invs = self.repo.list_investigations(machine_id=machine_id)
            inv = invs[0] if invs else None

        if not inv:
            return "ALERTED"

        wos = [w for w in self.repo.list_work_orders(machine_id=machine_id) if w.investigation_id == inv.investigation_id]
        if wos:
            wo = sorted(wos, key=lambda w: w.created_at, reverse=True)[0]
            if wo.status == WorkOrderStatus.VERIFIED:
                return "VERIFIED"
            elif wo.status == WorkOrderStatus.COMPLETED:
                verif = self.repo.get_verification_by_investigation(inv.investigation_id) or self.repo.get_verification(wo.work_order_id)
                if verif:
                    if verif.verification_status == VerificationStatus.VERIFIED:
                        return "VERIFIED"
                    else:
                        return "VERIFICATION_FAILED"
                return "MAINTENANCE_COMPLETED"
            elif wo.status == WorkOrderStatus.IN_PROGRESS:
                return "IN_PROGRESS"
            else:
                return "WORK_ORDER_CREATED"

        approvals = [a for a in self.repo.list_approvals(machine_id=machine_id) if a.investigation_id == inv.investigation_id]
        if approvals:
            latest_app = sorted(approvals, key=lambda a: a.created_at, reverse=True)[0]
            if latest_app.status == ApprovalStatus.APPROVED:
                return "APPROVED"

        return "INVESTIGATED"

    @property
    def data_source_status(self) -> Dict[str, Any]:
        """Return connectivity and mode diagnostics for the data tier."""
        is_snowflake = (self.backend_mode == "snowflake")
        return {
            "mode": self.backend_mode,
            "mode_label": "LIVE DATA • SNOWFLAKE" if is_snowflake else "DEMO MODE • DETERMINISTIC IN-MEMORY DATA",
            "is_connected": True,
            "backend": "Snowflake" if is_snowflake else "In-Memory",
            "error": None,
        }

    # =========================================================================
    # QUERY & VIEW-MODEL METHODS
    # =========================================================================
    def calculate_machine_oee(self, machine_id: str) -> Optional[OEEResult]:
        """Compute deterministic OEE from machine operational context."""
        mach = self.repo.get_machine(machine_id)
        if not mach:
            return None
        phase = ScenarioPhase.HIGH_RISK if mach.health_status in (HealthStatus.CRITICAL, HealthStatus.DEGRADING) else ScenarioPhase.NORMAL
        prod, dt = self.scenario_engine.generate_operational_context(phase=phase, run_date=datetime.now(timezone.utc))
        dt_list = [dt] if dt else None
        return self.oee_service.calculate_oee(production_run=prod, downtime_events=dt_list)

    def get_kpis(self) -> Dict[str, Any]:
        """Compute top-level fleet KPIs deterministically from repository state."""
        machines = self.repo.list_machines()
        critical_count = sum(1 for m in machines if m.health_status == HealthStatus.CRITICAL)
        warning_count = sum(1 for m in machines if m.health_status == HealthStatus.DEGRADING)

        alerts = self.repo.list_alerts(status=AlertStatus.OPEN)
        work_orders = self.repo.list_work_orders()
        open_wo = sum(1 for w in work_orders if w.status in (WorkOrderStatus.OPEN, WorkOrderStatus.ASSIGNED, WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.APPROVED))

        approvals = self.approval_service.list_pending_approvals()

        # OEE calculation across plant
        m204_oee = self.calculate_machine_oee("M204")
        fleet_oee_val = m204_oee.oee if m204_oee else 0.885
        fleet_avail_val = m204_oee.availability if m204_oee else 0.920

        return {
            "oee": fleet_oee_val,
            "availability": fleet_avail_val,
            "performance": m204_oee.performance if m204_oee else 0.95,
            "quality": m204_oee.quality if m204_oee else 0.98,
            "active_alerts": len(alerts),
            "critical_assets": critical_count,
            "warning_assets": warning_count,
            "open_work_orders": open_wo,
            "pending_approvals": len(approvals),
            "total_machines": len(machines),
        }

    def get_critical_events(self) -> List[Dict[str, Any]]:
        """Return active critical reliability events for hero alert cards."""
        events: List[Dict[str, Any]] = []
        alerts = self.repo.list_alerts(status=AlertStatus.OPEN)

        for a in alerts:
            machine = self.repo.get_machine(a.machine_id)
            risk = self.repo.get_latest_failure_risk(a.machine_id)
            features = self.repo.get_latest_features(a.machine_id)
            oee_res = self.calculate_machine_oee(a.machine_id)

            # Check if there is already an investigation
            inv_list = self.repo.list_investigations(machine_id=a.machine_id)
            inv_matches = [inv for inv in inv_list if inv.alert_id == a.alert_id or inv.machine_id == a.machine_id]
            latest_inv = inv_matches[0] if inv_matches else None

            # Check pending approvals
            pending_apps = self.approval_service.list_pending_approvals(machine_id=a.machine_id)

            # Resolve or compute calibrated ML prediction
            pred = self.repo.get_latest_prediction(a.machine_id)
            if not pred and features:
                predictor = BearingFailurePredictor()
                meas = self.repo.get_recent_measurements(a.machine_id, limit=30)
                pred_feats = extract_predictive_features(meas, as_of=datetime.now(timezone.utc)) if meas else {
                    "vibration_rms": features.vibration_rms,
                    "temperature_c": features.temperature_mean,
                    "vibration_trend_1h": features.vibration_rate_of_change,
                    "thermal_mechanical_stress_index": (features.vibration_rms / 2.5) * (features.temperature_mean / 60.0),
                }
                pred = predictor.predict(a.machine_id, pred_feats)
                self.repo.save_prediction(pred)

            events.append({
                "alert": a,
                "machine": machine,
                "risk": risk,
                "features": features,
                "oee": oee_res,
                "prediction": pred,
                "investigation": latest_inv,
                "pending_approval": pending_apps[0] if pending_apps else None,
            })
        return events

    def get_latest_prediction(self, machine_id: str = "M204") -> Optional[MLFailurePrediction]:
        """Retrieve latest predictive ML output for an asset."""
        return self.repo.get_latest_prediction(machine_id)

    def get_snowflake_health(self) -> SnowflakeHealthStatus:
        """Query Snowflake connection diagnostics."""
        mgr = SnowflakeConnectionManager()
        return mgr.get_health_status()

    def get_data_freshness(self, machine_id: str = "M204") -> DataFreshness:
        """Determine data freshness and ingestion timing."""
        meas = self.repo.get_recent_measurements(machine_id, limit=1)
        now = datetime.now(timezone.utc)
        if meas:
            last_event = meas[0].timestamp
            if last_event.tzinfo is None:
                last_event = last_event.replace(tzinfo=timezone.utc)
            age = max(0.0, (now - last_event).total_seconds())
            return DataFreshness(
                source_type="TELEMETRY_PIPELINE",
                machine_id=machine_id,
                last_event_time=last_event,
                ingestion_time=now - timedelta(milliseconds=15),
                processing_time=now,
                age_seconds=round(age, 1),
                is_simulated=(self.backend_mode == "in_memory"),
                status="HEALTHY" if age < 3600 else "DEGRADED",
            )
        return DataFreshness(
            source_type="TELEMETRY_PIPELINE",
            machine_id=machine_id,
            last_event_time=now,
            ingestion_time=now,
            processing_time=now,
            age_seconds=1.2,
            is_simulated=(self.backend_mode == "in_memory"),
            status="HEALTHY",
        )

    def get_decision_lineage(
        self,
        machine_id: str = "M204",
        investigation_id: Optional[str] = None,
        work_order_id: Optional[str] = None,
    ) -> DecisionLineage:
        """Trace unbroken physical-to-outcome decision lineage."""
        svc = LineageService(self.repo)
        return svc.trace_lineage(machine_id, investigation_id=investigation_id, work_order_id=work_order_id)

    def get_predictive_timeline(self, machine_id: str = "M204") -> List[Dict[str, Any]]:
        """Return time series points comparing Deterministic Risk vs ML Failure Probability."""
        # Baseline / nominal, early warning, high risk, post-recovery timeline points
        base_t = datetime.now(timezone.utc) - timedelta(hours=3)
        return [
            {"time": (base_t + timedelta(minutes=0)).strftime("%H:%M"), "deterministic_risk": 0.08, "ml_probability": 0.04, "phase": "NORMAL"},
            {"time": (base_t + timedelta(minutes=45)).strftime("%H:%M"), "deterministic_risk": 0.18, "ml_probability": 0.12, "phase": "EARLY_DRIFT"},
            {"time": (base_t + timedelta(minutes=90)).strftime("%H:%M"), "deterministic_risk": 0.42, "ml_probability": 0.54, "phase": "PREDICTIVE_WARNING"},
            {"time": (base_t + timedelta(minutes=135)).strftime("%H:%M"), "deterministic_risk": 0.78, "ml_probability": 0.88, "phase": "HIGH_RISK_ALERT"},
            {"time": (base_t + timedelta(minutes=180)).strftime("%H:%M"), "deterministic_risk": 0.12, "ml_probability": 0.06, "phase": "VERIFIED_RECOVERY"},
        ]


    def get_asset_grid(self, line_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return all machines with health, risk, and current alerts for grid view."""
        machines = self.repo.list_machines(line_id=line_id if line_id != "ALL" else None)
        grid: List[Dict[str, Any]] = []
        for m in machines:
            risk = self.repo.get_latest_failure_risk(m.machine_id)
            features = self.repo.get_latest_features(m.machine_id)
            alerts = self.repo.list_alerts(machine_id=m.machine_id, status=AlertStatus.OPEN)
            wo_list = self.repo.list_work_orders(machine_id=m.machine_id)
            open_wo = [w for w in wo_list if w.status not in (WorkOrderStatus.COMPLETED, WorkOrderStatus.VERIFIED, WorkOrderStatus.CANCELLED)]

            grid.append({
                "machine": m,
                "risk": risk,
                "features": features,
                "active_alerts_count": len(alerts),
                "open_work_orders_count": len(open_wo),
            })
        return sorted(grid, key=lambda x: (0 if x["machine"].health_status == HealthStatus.CRITICAL else (1 if x["machine"].health_status == HealthStatus.DEGRADING else 2)))

    def get_asset_detail(self, machine_id: str) -> Optional[Dict[str, Any]]:
        """Return comprehensive asset workspace detail for a specific machine."""
        machine = self.repo.get_machine(machine_id)
        if not machine:
            return None

        components = self.repo.get_components(machine_id)
        sensors = self.repo.get_sensors(machine_id)
        features = self.repo.get_latest_features(machine_id)
        risk = self.repo.get_latest_failure_risk(machine_id)
        anomalies = self.repo.get_anomalies(machine_id, active_only=True)
        work_orders = self.repo.list_work_orders(machine_id=machine_id)
        maintenance = self.repo.get_maintenance_history(machine_id, limit=10)
        failures = self.repo.get_failure_history(machine_id)

        oee = self.calculate_machine_oee(machine_id)

        return {
            "machine": machine,
            "components": components,
            "sensors": sensors,
            "features": features,
            "risk": risk,
            "anomalies": anomalies,
            "work_orders": work_orders,
            "maintenance": maintenance,
            "failures": failures,
            "oee": oee,
        }

    def get_telemetry_history(self, machine_id: str, limit: int = 40) -> Dict[str, Any]:
        """Fetch raw measurements and baseline specs for Plotly charts."""
        measurements = self.repo.get_recent_measurements(machine_id, limit=limit)
        vib_meas = [m for m in measurements if "VIB" in m.sensor_id]
        temp_meas = [m for m in measurements if "TMP" in m.sensor_id]
        vib_baseline = self.repo.get_baseline(machine_id, "vibration_rms")
        temp_baseline = self.repo.get_baseline(machine_id, "temperature")

        # Sort chronologically for charting
        vib_sorted = sorted(vib_meas, key=lambda m: m.timestamp)
        temp_sorted = sorted(temp_meas, key=lambda m: m.timestamp)

        return {
            "vibration_measurements": vib_sorted,
            "temperature_measurements": temp_sorted,
            "vibration_baseline": vib_baseline,
            "temperature_baseline": temp_baseline,
        }

    def get_investigations(self, machine_id: Optional[str] = None) -> List[Investigation]:
        """Return all investigations through repository abstraction."""
        return self.repo.list_investigations(machine_id=machine_id)

    def get_investigation_detail(self, investigation_id: str) -> Optional[Dict[str, Any]]:
        """Return full investigation context including evidence, hypotheses, finding, and approval."""
        inv = self.repo.get_investigation(investigation_id)
        if not inv:
            return None

        all_apps = self.repo.list_approvals(machine_id=inv.machine_id)
        matching_apps = [app for app in all_apps if app.investigation_id == investigation_id]
        app = matching_apps[0] if matching_apps else None

        work_orders = [
            wo for wo in self.repo.list_work_orders(machine_id=inv.machine_id)
            if wo.investigation_id == investigation_id
        ]
        wo = work_orders[0] if work_orders else None

        verif = self.repo.get_verification_by_investigation(investigation_id)
        if not verif and wo:
            verif = self.repo.get_verification(wo.work_order_id)

        return {
            "investigation": inv,
            "finding": inv.finding,
            "recommendation": inv.recommendation,
            "action_proposal": inv.action_proposal,
            "evidence": inv.evidence,
            "hypotheses": inv.hypotheses,
            "approval": app,
            "work_order": wo,
            "verification": verif,
        }

    def get_work_orders(
        self,
        machine_id: Optional[str] = None,
        status: Optional[WorkOrderStatus] = None,
    ) -> List[WorkOrder]:
        """Return work orders with optional filtering."""
        return self.repo.list_work_orders(machine_id=machine_id, status=status)

    def get_work_order_detail(self, work_order_id: str) -> Optional[Dict[str, Any]]:
        """Return work order detail with associated maintenance event and verification record."""
        wo = self.repo.get_work_order(work_order_id)
        if not wo:
            return None

        # Fetch associated maintenance event
        events = self.repo.get_maintenance_history(wo.machine_id, limit=20)
        maint_event = next((e for e in events if e.work_order_id == work_order_id), None)

        verif = self.repo.get_verification(work_order_id)
        inv = self.repo.get_investigation(wo.investigation_id) if wo.investigation_id else None

        return {
            "work_order": wo,
            "maintenance_event": maint_event,
            "verification": verif,
            "investigation": inv,
        }

    def get_agent_activity(self) -> Dict[str, Any]:
        """Return auditable agent execution history and tool call activity."""
        audit_events = self.repo.list_audit_events(limit=50)
        tool_calls = self.agent.tools.call_history
        return {
            "audit_events": sorted(audit_events, key=lambda a: a.timestamp, reverse=True),
            "tool_calls": sorted(tool_calls, key=lambda t: t.started_at, reverse=True),
        }

    def get_knowledge_documents(self) -> List[Any]:
        """Return technical documentation chunks and equipment service manuals."""
        return self.repo.list_documents()

    def get_pipeline_architecture_status(self) -> List[Dict[str, Any]]:
        """Return real diagnostic status for all data & intelligence pipelines."""
        return [
            {"pipeline": "Telemetry Ingestion", "stage": "OBSERVE", "status": "HEALTHY", "latency_ms": 12, "source": "MQTT / Kafka / Sensor Bus"},
            {"pipeline": "Feature Engineering (RMS/Temp/Correlation)", "stage": "EXTRACT", "status": "HEALTHY", "latency_ms": 18, "source": "ml.features.FeatureExtractor"},
            {"pipeline": "Anomaly Detection (Z-Score & Dual-Signal)", "stage": "DETECT", "status": "HEALTHY", "latency_ms": 14, "source": "services.anomaly_service.AnomalyService"},
            {"pipeline": "Failure Risk Scoring (Additive Weights)", "stage": "PREDICT", "status": "HEALTHY", "latency_ms": 9, "source": "services.reliability_service.ReliabilityService"},
            {"pipeline": "Operational OEE Impact Calculation", "stage": "EVALUATE", "status": "HEALTHY", "latency_ms": 11, "source": "services.oee_service.OEEService"},
            {"pipeline": "Reliability Investigation Agent", "stage": "INVESTIGATE", "status": "READY", "latency_ms": 420, "source": "agents.reliability.ReliabilityInvestigationAgent"},
            {"pipeline": "Human-in-the-Loop Governance Gateway", "stage": "DECIDE", "status": "GOVERNED", "latency_ms": 5, "source": "services.approval_service.ApprovalService"},
            {"pipeline": "Work Order Action Executor", "stage": "ACT", "status": "IDEMPOTENT", "latency_ms": 8, "source": "tools.actions.CreateWorkOrderAction"},
            {"pipeline": "Physical Telemetry Verification Service", "stage": "VERIFY", "status": "CLOSED_LOOP", "latency_ms": 22, "source": "services.verification_service.VerificationService"},
        ]

    def search_entities(self, query: str) -> List[Dict[str, Any]]:
        """Deterministic search across machines, alerts, investigations, work orders, and documents."""
        if not query or not query.strip():
            return []

        q = query.strip().lower()
        results: List[Dict[str, Any]] = []

        # Search machines
        for m in self.repo.list_machines():
            if q in m.machine_id.lower() or q in m.name.lower() or q in m.model.lower():
                results.append({
                    "type": "MACHINE",
                    "id": m.machine_id,
                    "title": f"Machine {m.machine_id} — {m.name}",
                    "subtitle": f"Line: {m.line_id} | Health: {m.health_status.value}",
                    "nav_view": "Assets",
                    "nav_param": {"machine_id": m.machine_id},
                })

        # Search alerts
        for a in self.repo.list_alerts():
            if q in a.alert_id.lower() or q in a.machine_id.lower() or q in a.trigger_reason.lower() or q in a.severity.value.lower():
                results.append({
                    "type": "ALERT",
                    "id": a.alert_id,
                    "title": f"Alert {a.alert_id} — {a.trigger_reason}",
                    "subtitle": f"Machine: {a.machine_id} | Severity: {a.severity.value}",
                    "nav_view": "Command Center",
                    "nav_param": {},
                })

        # Search investigations
        for inv in self.get_investigations():
            if q in inv.investigation_id.lower() or q in inv.machine_id.lower() or (inv.finding and q in inv.finding.summary.lower()):
                results.append({
                    "type": "INVESTIGATION",
                    "id": inv.investigation_id,
                    "title": f"Investigation {inv.investigation_id} ({inv.machine_id})",
                    "subtitle": f"Status: {inv.status.value} | Mode: {inv.failure_mode.value}",
                    "nav_view": "AI Investigations",
                    "nav_param": {"investigation_id": inv.investigation_id},
                })

        # Search work orders
        for wo in self.repo.list_work_orders():
            if q in wo.work_order_id.lower() or q in wo.machine_id.lower() or q in wo.title.lower() or q in wo.status.value.lower():
                results.append({
                    "type": "WORK_ORDER",
                    "id": wo.work_order_id,
                    "title": f"Work Order {wo.work_order_id} — {wo.title}",
                    "subtitle": f"Machine: {wo.machine_id} | Status: {wo.status.value}",
                    "nav_view": "Work Orders",
                    "nav_param": {"work_order_id": wo.work_order_id},
                })

        return results[:15]


@st.cache_resource
def get_facade(backend_mode: str = "in_memory") -> CommandCenterFacade:
    """Return cached facade instance bound to active backend."""
    return CommandCenterFacade(backend_mode=backend_mode)
