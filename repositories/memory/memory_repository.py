"""Deterministic in-memory repository implementing all domain interfaces.

Used for:
- Unit tests
- Local development & offline execution
- Fast CI runs
Pre-seeded with Plant 01, Line A/B/C, 10 machines, and primary machine M204.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from datetime import datetime, timezone
import threading

from domain.enums import AlertStatus, ApprovalStatus, HealthStatus, MachineState, WorkOrderStatus
from domain.models import (
    Alert,
    Anomaly,
    Approval,
    AuditEvent,
    Baseline,
    Component,
    Document,
    Evidence,
    Failure,
    FailureRisk,
    FeatureVector,
    HealthAssessment,
    Investigation,
    Machine,
    MaintenanceEvent,
    Plant,
    ProductionLine,
    Sensor,
    TelemetryMeasurement,
    Verification,
    WorkOrder,
)
from repositories.base import (
    GovernanceRepository,
    InvestigationRepository,
    KnowledgeRepository,
    MachineRepository,
    MaintenanceRepository,
    ReliabilityRepository,
    TelemetryRepository,
)
from data.generators.seed_data import (
    PLANT_01,
    LINES,
    MACHINES,
    M204_COMPONENTS,
    M204_SENSORS,
    M204_BASELINES,
    M204_FAILURES,
    M204_MAINTENANCE_HISTORY,
    M204_MANUAL,
)


def _safe_dt(dt: Optional[datetime]) -> datetime:
    if dt is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class InMemoryRepository(
    MachineRepository,
    TelemetryRepository,
    MaintenanceRepository,
    ReliabilityRepository,
    InvestigationRepository,
    GovernanceRepository,
    KnowledgeRepository,
):
    def __init__(self, seed: bool = True) -> None:
        self._lock = threading.RLock()
        self._plants: Dict[str, Plant] = {}
        self._lines: Dict[str, ProductionLine] = {}
        self._machines: Dict[str, Machine] = {}
        self._components: Dict[str, List[Component]] = {}
        self._sensors: Dict[str, List[Sensor]] = {}
        self._baselines: Dict[str, Dict[str, Baseline]] = {}  # machine_id -> signal_name -> Baseline
        self._measurements: Dict[str, List[TelemetryMeasurement]] = {}  # machine_id -> list
        self._features: Dict[str, List[FeatureVector]] = {}  # machine_id -> list
        self._anomalies: Dict[str, List[Anomaly]] = {}  # machine_id -> list
        self._failures: Dict[str, List[Failure]] = {}  # machine_id -> list
        self._maintenance_events: Dict[str, List[MaintenanceEvent]] = {}  # machine_id -> list
        self._failure_risks: Dict[str, List[FailureRisk]] = {}  # machine_id -> list
        self._health_assessments: Dict[str, HealthAssessment] = {}  # machine_id -> assessment
        self._alerts: Dict[str, Alert] = {}
        self._investigations: Dict[str, Investigation] = {}
        self._work_orders: Dict[str, WorkOrder] = {}
        self._approvals: Dict[str, Approval] = {}
        self._verifications: Dict[str, Verification] = {}  # work_order_id -> verification
        self._audit_events: List[AuditEvent] = []
        self._documents: Dict[str, Document] = {}  # machine_model -> Document

        if seed:
            self._seed_reference_data()

    def _seed_reference_data(self) -> None:
        with self._lock:
            self._plants[PLANT_01.plant_id] = PLANT_01
            for line in LINES:
                self._lines[line.line_id] = line
            for machine in MACHINES:
                self._machines[machine.machine_id] = machine
                self._components[machine.machine_id] = []
                self._sensors[machine.machine_id] = []
                self._measurements[machine.machine_id] = []
                self._features[machine.machine_id] = []
                self._anomalies[machine.machine_id] = []
                self._failures[machine.machine_id] = []
                self._maintenance_events[machine.machine_id] = []
                self._failure_risks[machine.machine_id] = []

            # Populate M204 deep profile
            self._components["M204"] = list(M204_COMPONENTS)
            self._sensors["M204"] = list(M204_SENSORS)
            self._baselines["M204"] = {b.signal_name: b for b in M204_BASELINES}
            self._failures["M204"] = list(M204_FAILURES)
            self._maintenance_events["M204"] = list(M204_MAINTENANCE_HISTORY)
            self._documents[M204_MANUAL.machine_model] = M204_MANUAL

            # Initial M204 health assessment
            self._health_assessments["M204"] = HealthAssessment(
                assessment_id="HA-M204-INIT",
                machine_id="M204",
                health_status=HealthStatus.HEALTHY,
                health_score=94.5,
                primary_concern=None,
            )

    # MachineRepository implementations
    def get_plant(self, plant_id: str) -> Optional[Plant]:
        with self._lock:
            return self._plants.get(plant_id)

    def list_lines(self, plant_id: str) -> List[ProductionLine]:
        with self._lock:
            return [line for line in self._lines.values() if line.plant_id == plant_id]

    def get_machine(self, machine_id: str) -> Optional[Machine]:
        with self._lock:
            return self._machines.get(machine_id)

    def list_machines(self, line_id: Optional[str] = None) -> List[Machine]:
        with self._lock:
            if line_id:
                return [m for m in self._machines.values() if m.line_id == line_id]
            return list(self._machines.values())

    def get_components(self, machine_id: str) -> List[Component]:
        with self._lock:
            return list(self._components.get(machine_id, []))

    def get_sensors(self, machine_id: str) -> List[Sensor]:
        with self._lock:
            return list(self._sensors.get(machine_id, []))

    def update_machine_health(
        self, machine_id: str, health_status: HealthStatus, state: Optional[MachineState] = None
    ) -> Machine:
        with self._lock:
            machine = self._machines.get(machine_id)
            if not machine:
                raise ValueError(f"Machine {machine_id} does not exist")
            updated = machine.model_copy(
                update={"health_status": health_status, **({"state": state} if state else {})}
            )
            self._machines[machine_id] = updated
            return updated

    # TelemetryRepository implementations
    def save_measurements(self, measurements: List[TelemetryMeasurement]) -> None:
        with self._lock:
            for m in measurements:
                self._measurements.setdefault(m.machine_id, []).append(m)

    def get_recent_measurements(
        self, machine_id: str, sensor_id: Optional[str] = None, limit: int = 100
    ) -> List[TelemetryMeasurement]:
        with self._lock:
            items = self._measurements.get(machine_id, [])
            if sensor_id:
                items = [m for m in items if m.sensor_id == sensor_id]
            return sorted(items, key=lambda m: m.timestamp, reverse=True)[:limit]

    def save_feature(self, feature: FeatureVector) -> None:
        with self._lock:
            self._features.setdefault(feature.machine_id, []).append(feature)

    def get_latest_features(self, machine_id: str) -> Optional[FeatureVector]:
        with self._lock:
            items = self._features.get(machine_id, [])
            if not items:
                return None
            return sorted(items, key=lambda f: f.timestamp, reverse=True)[0]

    def get_baseline(self, machine_id: str, signal_name: str) -> Optional[Baseline]:
        with self._lock:
            return self._baselines.get(machine_id, {}).get(signal_name)

    def save_anomaly(self, anomaly: Anomaly) -> None:
        with self._lock:
            self._anomalies.setdefault(anomaly.machine_id, []).append(anomaly)

    def get_anomalies(self, machine_id: str, active_only: bool = True) -> List[Anomaly]:
        with self._lock:
            items = self._anomalies.get(machine_id, [])
            if active_only:
                items = [a for a in items if a.status == "ACTIVE"]
            return sorted(items, key=lambda a: a.detected_at, reverse=True)

    # MaintenanceRepository implementations
    def get_maintenance_history(self, machine_id: str, limit: int = 20) -> List[MaintenanceEvent]:
        with self._lock:
            items = self._maintenance_events.get(machine_id, [])
            return sorted(items, key=lambda m: _safe_dt(m.performed_at), reverse=True)[:limit]

    def save_maintenance_event(self, event: MaintenanceEvent) -> None:
        with self._lock:
            self._maintenance_events.setdefault(event.machine_id, []).append(event)

    def create_work_order(self, work_order: WorkOrder) -> WorkOrder:
        with self._lock:
            if work_order.idempotency_key:
                for existing in self._work_orders.values():
                    if existing.idempotency_key == work_order.idempotency_key:
                        return existing
            self._work_orders[work_order.work_order_id] = work_order
            return work_order

    def get_work_order(self, work_order_id: str) -> Optional[WorkOrder]:
        with self._lock:
            return self._work_orders.get(work_order_id)

    def list_work_orders(
        self, machine_id: Optional[str] = None, status: Optional[WorkOrderStatus] = None
    ) -> List[WorkOrder]:
        with self._lock:
            res = list(self._work_orders.values())
            if machine_id:
                res = [wo for wo in res if wo.machine_id == machine_id]
            if status:
                res = [wo for wo in res if wo.status == status]
            return sorted(res, key=lambda wo: wo.created_at, reverse=True)

    def update_work_order_status(self, work_order_id: str, status: WorkOrderStatus) -> WorkOrder:
        with self._lock:
            wo = self._work_orders.get(work_order_id)
            if not wo:
                raise ValueError(f"WorkOrder {work_order_id} not found")
            updated = wo.model_copy(update={"status": status})
            self._work_orders[work_order_id] = updated
            return updated

    def update_work_order(self, work_order: WorkOrder) -> WorkOrder:
        with self._lock:
            if work_order.work_order_id not in self._work_orders:
                raise ValueError(f"WorkOrder {work_order.work_order_id} not found")
            self._work_orders[work_order.work_order_id] = work_order
            return work_order

    # ReliabilityRepository implementations
    def get_failure_history(self, machine_id: str) -> List[Failure]:
        with self._lock:
            items = self._failures.get(machine_id, [])
            return sorted(items, key=lambda f: f.occurred_at, reverse=True)

    def save_failure_risk(self, risk: FailureRisk) -> None:
        with self._lock:
            self._failure_risks.setdefault(risk.machine_id, []).append(risk)

    def get_latest_failure_risk(self, machine_id: str) -> Optional[FailureRisk]:
        with self._lock:
            items = self._failure_risks.get(machine_id, [])
            if not items:
                return None
            return sorted(items, key=lambda r: r.prediction_timestamp, reverse=True)[0]

    def save_health_assessment(self, assessment: HealthAssessment) -> None:
        with self._lock:
            self._health_assessments[assessment.machine_id] = assessment

    def get_latest_health_assessment(self, machine_id: str) -> Optional[HealthAssessment]:
        with self._lock:
            return self._health_assessments.get(machine_id)

    # InvestigationRepository implementations
    def create_alert(self, alert: Alert) -> Alert:
        with self._lock:
            self._alerts[alert.alert_id] = alert
            return alert

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        with self._lock:
            return self._alerts.get(alert_id)

    def list_alerts(
        self, machine_id: Optional[str] = None, status: Optional[AlertStatus] = None
    ) -> List[Alert]:
        with self._lock:
            res = list(self._alerts.values())
            if machine_id:
                res = [a for a in res if a.machine_id == machine_id]
            if status:
                res = [a for a in res if a.status == status]
            return sorted(res, key=lambda a: a.created_at, reverse=True)

    def create_investigation(self, investigation: Investigation) -> Investigation:
        with self._lock:
            self._investigations[investigation.investigation_id] = investigation
            return investigation

    def get_investigation(self, investigation_id: str) -> Optional[Investigation]:
        with self._lock:
            return self._investigations.get(investigation_id)

    def save_evidence(self, evidence: List[Evidence]) -> None:
        with self._lock:
            for ev in evidence:
                inv = self._investigations.get(ev.investigation_id)
                if inv:
                    inv.evidence.append(ev)

    def update_investigation(self, investigation: Investigation) -> Investigation:
        with self._lock:
            self._investigations[investigation.investigation_id] = investigation
            return investigation

    # GovernanceRepository implementations
    def create_approval(self, approval: Approval) -> Approval:
        with self._lock:
            self._approvals[approval.approval_id] = approval
            return approval

    def get_approval(self, approval_id: str) -> Optional[Approval]:
        with self._lock:
            return self._approvals.get(approval_id)

    def list_approvals(
        self, machine_id: Optional[str] = None, status: Optional[ApprovalStatus] = None
    ) -> List[Approval]:
        with self._lock:
            res = list(self._approvals.values())
            if machine_id:
                res = [app for app in res if app.machine_id == machine_id]
            if status:
                res = [app for app in res if app.status == status]
            return sorted(res, key=lambda app: app.created_at, reverse=True)

    def update_approval(
        self, approval_id: str, status: ApprovalStatus, reviewer: str, reason: str
    ) -> Approval:
        with self._lock:
            app = self._approvals.get(approval_id)
            if not app:
                raise ValueError(f"Approval {approval_id} not found")
            updated = app.model_copy(
                update={
                    "status": status,
                    "reviewed_by": reviewer,
                    "decision_reason": reason,
                }
            )
            self._approvals[approval_id] = updated
            return updated

    def save_verification(self, verification: Verification) -> None:
        with self._lock:
            self._verifications[verification.work_order_id] = verification

    def get_verification(self, work_order_id: str) -> Optional[Verification]:
        with self._lock:
            return self._verifications.get(work_order_id)

    def log_audit(self, event: AuditEvent) -> None:
        with self._lock:
            self._audit_events.append(event)

    # KnowledgeRepository implementations
    def get_manual(self, machine_model: str) -> Optional[Document]:
        with self._lock:
            return self._documents.get(machine_model)

    def search_docs(self, query: str) -> List[str]:
        with self._lock:
            results: List[str] = []
            q_lower = query.lower()
            for doc in self._documents.values():
                for chunk in doc.chunks:
                    if q_lower in chunk.content.lower() or any(q_lower in tag.lower() for tag in chunk.tags):
                        results.append(f"[{doc.title} - {chunk.section_title}]: {chunk.content}")
            return results
