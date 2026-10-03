"""Deterministic in-memory repository implementing all domain interfaces.

Used for:
- Unit tests
- Local development & offline execution
- Fast CI runs
Pre-seeded with Plant 01, Line A/B/C, 10 machines, and primary machine M204.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from datetime import date, datetime, timezone
import json
import threading

from domain.enums import AlertStatus, ApprovalStatus, FailureMode, HealthStatus, MachineState, WorkOrderStatus
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
    Finding,
    HealthAssessment,
    Hypothesis,
    Investigation,
    Machine,
    MaintenanceEvent,
    Plant,
    ProductionLine,
    Recommendation,
    Sensor,
    TelemetryMeasurement,
    ToolCall,
    Verification,
    VerificationResult,
    VerificationPolicy,
    ActionProposal,
    ActionExecution,
    ActionOutcome,
    WorkOrder,
    MLFailurePrediction,
    PredictionOutcome,
    CanonicalPrediction,
    Product,
    ProductionOrder,
    PurchaseOrder,
    SparePart,
    Supplier,
    WorkOrderPartUsage,
    KnowledgeDocument,
    FailureModeTaxonomy,
    MachineHealthDaily,
    MachineOEEDaily,
    DowntimeSummary,
    MaintenanceSummary,
    InventoryRisk,
    ProductionContext,
    ReliabilityFeatures,
    ModelRegistryRecord,
    ModelEvaluationRecord,
    PredictionFeatureSnapshot,
    PredictionLineage,
)
from repositories.base import (
    GovernanceRepository,
    InvestigationRepository,
    KnowledgeRepository,
    MachineRepository,
    MaintenanceRepository,
    ReliabilityRepository,
    SupplyChainRepository,
    TelemetryRepository,
    AnalyticsRepository,
    KnowledgeSearchRepository,
    MLRepository,
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
from data.generators.canonical_fixtures import (
    CANONICAL_PLANT,
    CANONICAL_LINES,
    CANONICAL_MACHINES,
    CANONICAL_COMPONENTS,
    CANONICAL_SENSORS,
    CANONICAL_SPARE_PARTS,
    CANONICAL_SUPPLIERS,
    CANONICAL_PURCHASE_ORDERS,
    CANONICAL_PRODUCTION_ORDERS,
    CANONICAL_PREDICTIONS,
    CANONICAL_FAILURE_MODES,
    CANONICAL_KNOWLEDGE_DOCS,
    CANONICAL_HEALTH_DAILY,
    CANONICAL_OEE_DAILY,
    CANONICAL_DOWNTIME_DAILY,
    CANONICAL_MAINTENANCE_DAILY,
    CANONICAL_INVENTORY_RISKS,
    CANONICAL_PRODUCTION_CONTEXTS,
    CANONICAL_RELIABILITY_FEATURES,
)


def _safe_dt(dt: Optional[datetime]) -> datetime:
    if dt is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _canonical_to_ml_prediction(cp: CanonicalPrediction) -> MLFailurePrediction:
    """Map canonical CORE.PREDICTION record into domain MLFailurePrediction."""
    comp_id = (cp.suspected_component_id or "").upper()
    if "BRG" in comp_id or "BEARING" in comp_id:
        fmode = FailureMode.BEARING_DEGRADATION
    elif "MTR" in comp_id or "MOTOR" in comp_id:
        fmode = FailureMode.MOTOR_OVERHEATING
    elif "HYD" in comp_id:
        fmode = FailureMode.MECHANICAL_WEAR
    elif "GRB" in comp_id or "GEAR" in comp_id:
        fmode = FailureMode.MECHANICAL_WEAR
    else:
        fmode = FailureMode.BEARING_DEGRADATION

    top_feats: Dict[str, float] = {}
    if cp.top_features:
        try:
            parsed = json.loads(cp.top_features) if isinstance(cp.top_features, str) else cp.top_features
            if isinstance(parsed, dict):
                top_feats = {str(k): float(v) for k, v in parsed.items()}
            elif isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and "feature" in item and "share" in item:
                        top_feats[str(item["feature"])] = float(item["share"])
                    elif isinstance(item, dict) and len(item) == 1:
                        k, v = next(iter(item.items()))
                        top_feats[str(k)] = float(v)
        except Exception:
            top_feats = {}

    horizon_hours = int(cp.horizon_days) * 24 if cp.horizon_days else 168
    scored_ts = cp.scored_ts
    if isinstance(scored_ts, str):
        try:
            scored_ts = datetime.fromisoformat(scored_ts)
        except Exception:
            scored_ts = datetime.now(timezone.utc)

    prob = float(cp.failure_prob)
    return MLFailurePrediction(
        prediction_id=cp.prediction_id,
        machine_id=cp.machine_id,
        component_id=cp.suspected_component_id,
        failure_mode=fmode,
        failure_probability=prob,
        prediction_horizon_hours=horizon_hours,
        model_name=cp.model_name,
        model_version="1.0.0",
        training_dataset_version="v2026.03-canonical",
        feature_schema_version="v1.0-29feat",
        confidence=0.95 if prob >= 0.70 else 0.88,
        threshold_exceeded=prob >= 0.40,
        top_contributing_features=top_feats,
        feature_timestamp=scored_ts,
        prediction_timestamp=scored_ts,
    )


class InMemoryRepository(
    MachineRepository,
    TelemetryRepository,
    MaintenanceRepository,
    ReliabilityRepository,
    InvestigationRepository,
    GovernanceRepository,
    KnowledgeRepository,
    SupplyChainRepository,
    AnalyticsRepository,
    KnowledgeSearchRepository,
    MLRepository,
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
        self._audit_events: List[AuditEvent] = []
        self._documents: Dict[str, Document] = {}  # machine_model -> Document
        self._verifications: Dict[str, Verification] = {}  # work_order_id -> Verification
        self._predictions: Dict[str, List[MLFailurePrediction]] = {}  # machine_id -> list
        self._prediction_outcomes: Dict[str, PredictionOutcome] = {}  # prediction_id -> outcome
        self._spare_parts: Dict[str, SparePart] = {}
        self._suppliers: Dict[str, Supplier] = {}
        self._purchase_orders: Dict[str, PurchaseOrder] = {}
        self._production_orders: Dict[str, ProductionOrder] = {}
        self._canonical_predictions: Dict[str, CanonicalPrediction] = {}
        self._health_daily: Dict[Tuple[str, date], MachineHealthDaily] = {}
        self._oee_daily: Dict[Tuple[str, date], MachineOEEDaily] = {}
        self._downtime_daily: Dict[Tuple[str, date], DowntimeSummary] = {}
        self._maintenance_daily: Dict[Tuple[str, date], MaintenanceSummary] = {}
        self._inventory_risks: Dict[str, InventoryRisk] = {}
        self._production_contexts: Dict[str, ProductionContext] = {}
        self._reliability_features: Dict[Tuple[str, date], ReliabilityFeatures] = {}
        self._knowledge_documents: Dict[str, KnowledgeDocument] = {}
        self._failure_modes: Dict[str, FailureModeTaxonomy] = {}
        self._models: Dict[str, ModelRegistryRecord] = {}
        self._evaluations: Dict[str, List[ModelEvaluationRecord]] = {}
        self._prediction_snapshots: Dict[str, PredictionFeatureSnapshot] = {}
        self._prediction_lineages: Dict[str, PredictionLineage] = {}
        self._action_proposals: Dict[str, ActionProposal] = {}
        self._action_executions: Dict[str, ActionExecution] = {}
        self._action_outcomes: Dict[str, ActionOutcome] = {}
        self._verification_policies: Dict[str, VerificationPolicy] = {}
        self._hypotheses: Dict[str, List[Hypothesis]] = {}
        self._findings: Dict[str, List[Finding]] = {}
        self._recommendations: Dict[str, List[Recommendation]] = {}
        self._tool_calls: Dict[str, List[ToolCall]] = {}

        if seed:
            self._seed_reference_data()

    def _seed_reference_data(self) -> None:
        with self._lock:
            # 1. Seed legacy M204 plant and machines (for regression baseline)
            self._plants[PLANT_01.plant_id] = PLANT_01
            for line in LINES:
                self._lines[line.line_id] = line
            for machine in MACHINES:
                if not machine.plant_id:
                    line_obj = self._lines.get(machine.line_id)
                    p_id = line_obj.plant_id if line_obj else PLANT_01.plant_id
                    machine = machine.model_copy(update={"plant_id": p_id})
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

            # 2. Seed canonical 25-machine factory dataset & spotlight entities (M21, M15, M05)
            self._plants[CANONICAL_PLANT.plant_id] = CANONICAL_PLANT
            for line in CANONICAL_LINES:
                self._lines[line.line_id] = line
            for machine in CANONICAL_MACHINES:
                if not machine.plant_id:
                    line_obj = self._lines.get(machine.line_id)
                    p_id = line_obj.plant_id if line_obj else CANONICAL_PLANT.plant_id
                    machine = machine.model_copy(update={"plant_id": p_id})
                self._machines[machine.machine_id] = machine
                if machine.machine_id not in self._components:
                    self._components[machine.machine_id] = []
                if machine.machine_id not in self._sensors:
                    self._sensors[machine.machine_id] = []
                if machine.machine_id not in self._measurements:
                    self._measurements[machine.machine_id] = []
                if machine.machine_id not in self._features:
                    self._features[machine.machine_id] = []
                if machine.machine_id not in self._anomalies:
                    self._anomalies[machine.machine_id] = []
                if machine.machine_id not in self._failures:
                    self._failures[machine.machine_id] = []
                if machine.machine_id not in self._maintenance_events:
                    self._maintenance_events[machine.machine_id] = []
                if machine.machine_id not in self._failure_risks:
                    self._failure_risks[machine.machine_id] = []

            for comp in CANONICAL_COMPONENTS:
                self._components[comp.machine_id].append(comp)

            for sens in CANONICAL_SENSORS:
                self._sensors[sens.machine_id].append(sens)

            for part in CANONICAL_SPARE_PARTS:
                self._spare_parts[part.part_id] = part

            for sup in CANONICAL_SUPPLIERS:
                self._suppliers[sup.supplier_id] = sup

            for po in CANONICAL_PURCHASE_ORDERS:
                self._purchase_orders[po.po_id] = po

            for prd in CANONICAL_PRODUCTION_ORDERS:
                self._production_orders[prd.production_order_id] = prd

            for pred in CANONICAL_PREDICTIONS:
                self._canonical_predictions[pred.prediction_id] = pred

            for h in CANONICAL_HEALTH_DAILY:
                self._health_daily[(h.machine_id, h.metric_date)] = h

            for o in CANONICAL_OEE_DAILY:
                self._oee_daily[(o.machine_id, o.metric_date)] = o

            for d in CANONICAL_DOWNTIME_DAILY:
                self._downtime_daily[(d.machine_id, d.metric_date)] = d

            for m in CANONICAL_MAINTENANCE_DAILY:
                self._maintenance_daily[(m.machine_id, m.metric_date)] = m

            for ir in CANONICAL_INVENTORY_RISKS:
                self._inventory_risks[ir.part_id] = ir

            for pc in CANONICAL_PRODUCTION_CONTEXTS:
                self._production_contexts[pc.production_order_id] = pc

            for rf in CANONICAL_RELIABILITY_FEATURES:
                self._reliability_features[(rf.machine_id, rf.feature_date)] = rf

            for fm in CANONICAL_FAILURE_MODES:
                self._failure_modes[fm.failure_code] = fm

            for doc in CANONICAL_KNOWLEDGE_DOCS:
                self._knowledge_documents[doc.document_id] = doc

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

    def reset_state(self) -> None:
        """Reset repository to initial clean healthy baseline state."""
        with self._lock:
            self._plants.clear()
            self._lines.clear()
            self._machines.clear()
            self._components.clear()
            self._sensors.clear()
            self._baselines.clear()
            self._measurements.clear()
            self._features.clear()
            self._anomalies.clear()
            self._failures.clear()
            self._maintenance_events.clear()
            self._failure_risks.clear()
            self._health_assessments.clear()
            self._alerts.clear()
            self._investigations.clear()
            self._work_orders.clear()
            self._approvals.clear()
            self._verifications.clear()
            self._audit_events.clear()
            self._documents.clear()
            self._predictions.clear()
            self._prediction_outcomes.clear()
            self._action_proposals.clear()
            self._action_executions.clear()
            self._action_outcomes.clear()
            self._verification_policies.clear()
            self._seed_reference_data()

    def get_anomalies(self, machine_id: str, active_only: bool = True) -> List[Anomaly]:
        with self._lock:
            items = self._anomalies.get(machine_id, [])
            if active_only:
                items = [a for a in items if a.status == "ACTIVE"]
            return sorted(items, key=lambda a: a.detected_at, reverse=True)

    def list_anomalies(self, machine_id: Optional[str] = None, active_only: bool = True) -> List[Anomaly]:
        with self._lock:
            all_anomalies: List[Anomaly] = []
            if machine_id:
                all_anomalies = list(self._anomalies.get(machine_id, []))
            else:
                for lst in self._anomalies.values():
                    all_anomalies.extend(lst)
            if active_only:
                all_anomalies = [a for a in all_anomalies if a.status == "ACTIVE"]
            return sorted(all_anomalies, key=lambda a: a.detected_at, reverse=True)

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

    def get_downtime_event_count(self, machine_id: str) -> int:
        with self._lock:
            return len(self._failures.get(machine_id, []))

    def save_failure_risk(self, risk: FailureRisk) -> None:
        with self._lock:
            self._failure_risks.setdefault(risk.machine_id, []).append(risk)

    def get_latest_failure_risk(self, machine_id: str) -> Optional[FailureRisk]:
        with self._lock:
            items = self._failure_risks.get(machine_id, [])
            if not items:
                return None
            return sorted(items, key=lambda r: r.prediction_timestamp, reverse=True)[0]

    def get_latest_failure_risks(
        self, machine_ids: Optional[List[str]] = None
    ) -> Dict[str, FailureRisk]:
        with self._lock:
            target_ids = machine_ids if machine_ids is not None else list(self._failure_risks.keys())
            results = {}
            for m_id in target_ids:
                items = self._failure_risks.get(m_id, [])
                if items:
                    results[m_id] = sorted(items, key=lambda r: r.prediction_timestamp, reverse=True)[0]
            return results

    def save_health_assessment(self, assessment: HealthAssessment) -> None:
        with self._lock:
            self._health_assessments[assessment.machine_id] = assessment

    def get_latest_health_assessment(self, machine_id: str) -> Optional[HealthAssessment]:
        with self._lock:
            return self._health_assessments.get(machine_id)

    def save_prediction(self, prediction: MLFailurePrediction) -> None:
        with self._lock:
            self._predictions.setdefault(prediction.machine_id, []).append(prediction)

    def get_latest_prediction(self, machine_id: str) -> Optional[MLFailurePrediction]:
        with self._lock:
            items = self._predictions.get(machine_id, [])
            if items:
                return sorted(items, key=lambda p: p.prediction_timestamp, reverse=True)[0]
            cpreds = self.list_canonical_predictions(machine_id=machine_id, limit=1)
            if cpreds:
                return _canonical_to_ml_prediction(cpreds[0])
            return None

    def get_latest_predictions(
        self, machine_ids: Optional[List[str]] = None
    ) -> Dict[str, MLFailurePrediction]:
        with self._lock:
            target_ids = machine_ids if machine_ids is not None else list(set(list(self._predictions.keys()) + [cp.machine_id for cp in self._canonical_predictions]))
            results = {}
            for m_id in target_ids:
                pred = self.get_latest_prediction(m_id)
                if pred:
                    results[m_id] = pred
            return results

    def list_predictions(
        self, machine_id: Optional[str] = None, limit: int = 50
    ) -> List[MLFailurePrediction]:
        with self._lock:
            if machine_id:
                items = list(self._predictions.get(machine_id, []))
            else:
                items = [p for sub in self._predictions.values() for p in sub]
            if not items:
                cpreds = self.list_canonical_predictions(machine_id=machine_id, limit=limit)
                return [_canonical_to_ml_prediction(cp) for cp in cpreds]
            return sorted(items, key=lambda p: p.prediction_timestamp, reverse=True)[:limit]

    def save_prediction_outcome(self, outcome: PredictionOutcome) -> None:
        with self._lock:
            self._prediction_outcomes[outcome.prediction_id] = outcome

    def get_prediction_outcome(self, prediction_id: str) -> Optional[PredictionOutcome]:
        with self._lock:
            return self._prediction_outcomes.get(prediction_id)

    def list_prediction_outcomes(
        self, machine_id: Optional[str] = None
    ) -> List[PredictionOutcome]:
        with self._lock:
            res = list(self._prediction_outcomes.values())
            if machine_id:
                res = [o for o in res if o.machine_id == machine_id]
            return sorted(res, key=lambda o: o.evaluated_at, reverse=True)

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

    def get_evidence(self, investigation_id: str) -> List[Evidence]:
        with self._lock:
            inv = self._investigations.get(investigation_id)
            return list(inv.evidence) if inv else []

    def save_evidence(self, evidence: List[Evidence]) -> None:
        with self._lock:
            for ev in evidence:
                inv = self._investigations.get(ev.investigation_id)
                if inv:
                    existing_ids = {e.evidence_id for e in inv.evidence}
                    if ev.evidence_id not in existing_ids:
                        inv.evidence.append(ev)

    def save_hypotheses(self, hypotheses: List[Hypothesis]) -> None:
        with self._lock:
            for hyp in hypotheses:
                inv_list = self._hypotheses.setdefault(hyp.investigation_id, [])
                existing_ids = {h.hypothesis_id for h in inv_list}
                if hyp.hypothesis_id not in existing_ids:
                    inv_list.append(hyp)
                else:
                    # Update existing
                    self._hypotheses[hyp.investigation_id] = [
                        hyp if h.hypothesis_id == hyp.hypothesis_id else h for h in inv_list
                    ]
                inv = self._investigations.get(hyp.investigation_id)
                if inv:
                    inv_h_ids = {h.hypothesis_id for h in inv.hypotheses}
                    if hyp.hypothesis_id not in inv_h_ids:
                        inv.hypotheses.append(hyp)
                    else:
                        inv.hypotheses = [
                            hyp if h.hypothesis_id == hyp.hypothesis_id else h for h in inv.hypotheses
                        ]

    def get_hypotheses(self, investigation_id: str) -> List[Hypothesis]:
        with self._lock:
            inv = self._investigations.get(investigation_id)
            if inv and inv.hypotheses:
                return list(inv.hypotheses)
            return list(self._hypotheses.get(investigation_id, []))

    def save_findings(self, findings: List[Finding]) -> None:
        with self._lock:
            for f in findings:
                inv_list = self._findings.setdefault(f.investigation_id, [])
                existing_ids = {item.finding_id for item in inv_list}
                if f.finding_id not in existing_ids:
                    inv_list.append(f)
                else:
                    self._findings[f.investigation_id] = [
                        f if item.finding_id == f.finding_id else item for item in inv_list
                    ]
                inv = self._investigations.get(f.investigation_id)
                if inv:
                    inv_f_ids = {item.finding_id for item in inv.findings}
                    if f.finding_id not in inv_f_ids:
                        inv.findings.append(f)
                    else:
                        inv.findings = [
                            f if item.finding_id == f.finding_id else item for item in inv.findings
                        ]
                    if not inv.finding:
                        inv.finding = f

    def get_findings(self, investigation_id: str) -> List[Finding]:
        with self._lock:
            inv = self._investigations.get(investigation_id)
            if inv and inv.findings:
                return list(inv.findings)
            return list(self._findings.get(investigation_id, []))

    def save_recommendations(self, recommendations: List[Recommendation]) -> None:
        with self._lock:
            for r in recommendations:
                inv_list = self._recommendations.setdefault(r.investigation_id, [])
                existing_ids = {item.recommendation_id for item in inv_list}
                if r.recommendation_id not in existing_ids:
                    inv_list.append(r)
                else:
                    self._recommendations[r.investigation_id] = [
                        r if item.recommendation_id == r.recommendation_id else item for item in inv_list
                    ]
                inv = self._investigations.get(r.investigation_id)
                if inv:
                    inv_r_ids = {item.recommendation_id for item in inv.recommendations}
                    if r.recommendation_id not in inv_r_ids:
                        inv.recommendations.append(r)
                    else:
                        inv.recommendations = [
                            r if item.recommendation_id == r.recommendation_id else item for item in inv.recommendations
                        ]
                    if not inv.recommendation:
                        inv.recommendation = r

    def get_recommendations(self, investigation_id: str) -> List[Recommendation]:
        with self._lock:
            inv = self._investigations.get(investigation_id)
            if inv and inv.recommendations:
                return list(inv.recommendations)
            return list(self._recommendations.get(investigation_id, []))

    def save_tool_calls(
        self, tool_calls: List[ToolCall], investigation_id: Optional[str] = None
    ) -> None:
        with self._lock:
            for tc in tool_calls:
                inv_id = investigation_id or tc.execution_id or "ADHOC"
                inv_list = self._tool_calls.setdefault(inv_id, [])
                existing_ids = {item.tool_call_id for item in inv_list}
                if tc.tool_call_id not in existing_ids:
                    inv_list.append(tc)
                else:
                    self._tool_calls[inv_id] = [
                        tc if item.tool_call_id == tc.tool_call_id else item for item in inv_list
                    ]

    def get_tool_calls(self, investigation_id: str) -> List[ToolCall]:
        with self._lock:
            return list(self._tool_calls.get(investigation_id, []))

    def save_investigation_bundle(
        self,
        investigation: Investigation,
        evidence: Optional[List[Evidence]] = None,
        hypotheses: Optional[List[Hypothesis]] = None,
        findings: Optional[List[Finding]] = None,
        recommendations: Optional[List[Recommendation]] = None,
        tool_calls: Optional[List[ToolCall]] = None,
    ) -> Investigation:
        with self._lock:
            self.create_investigation(investigation)
            inv = self._investigations.get(investigation.investigation_id)
            if evidence is not None:
                if inv:
                    inv.evidence = []
                self.save_evidence(evidence)
            if hypotheses is not None:
                self._hypotheses[investigation.investigation_id] = []
                if inv:
                    inv.hypotheses = []
                self.save_hypotheses(hypotheses)
            if findings is not None:
                self._findings[investigation.investigation_id] = []
                if inv:
                    inv.findings = []
                    inv.finding = None
                self.save_findings(findings)
            if recommendations is not None:
                self._recommendations[investigation.investigation_id] = []
                if inv:
                    inv.recommendations = []
                    inv.recommendation = None
                self.save_recommendations(recommendations)
            if tool_calls:
                self.save_tool_calls(tool_calls, investigation_id=investigation.investigation_id)
            return investigation

    def update_investigation(self, investigation: Investigation) -> Investigation:
        with self._lock:
            self._investigations[investigation.investigation_id] = investigation
            return investigation

    def list_investigations(self, machine_id: Optional[str] = None) -> List[Investigation]:
        with self._lock:
            res = list(self._investigations.values())
            if machine_id:
                res = [inv for inv in res if inv.machine_id == machine_id]
            return sorted(res, key=lambda inv: inv.created_at, reverse=True)

    def get_investigation_by_alert(self, alert_id: str) -> Optional[Investigation]:
        with self._lock:
            for inv in self._investigations.values():
                if inv.alert_id == alert_id:
                    return inv
            return None

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

    def get_verification_by_investigation(self, investigation_id: str) -> Optional[Verification]:
        with self._lock:
            for v in self._verifications.values():
                if v.investigation_id == investigation_id:
                    return v
            return None

    def list_verifications(self, machine_id: Optional[str] = None) -> List[Verification]:
        with self._lock:
            res = list(self._verifications.values())
            if machine_id:
                res = [v for v in res if v.machine_id == machine_id]
            return sorted(res, key=lambda v: _safe_dt(v.verified_at), reverse=True)

    def log_audit(self, event: AuditEvent) -> None:
        with self._lock:
            self._audit_events.append(event)

    def list_audit_events(self, limit: int = 50) -> List[AuditEvent]:
        with self._lock:
            return sorted(self._audit_events, key=lambda a: a.timestamp, reverse=True)[:limit]

    def save_action_proposal(self, proposal: ActionProposal) -> ActionProposal:
        with self._lock:
            if proposal.idempotency_key:
                for existing in self._action_proposals.values():
                    if existing.idempotency_key == proposal.idempotency_key:
                        return existing
            self._action_proposals[proposal.action_proposal_id] = proposal
            return proposal

    def get_action_proposal(self, action_proposal_id: str) -> Optional[ActionProposal]:
        with self._lock:
            return self._action_proposals.get(action_proposal_id)

    def list_action_proposals(
        self, machine_id: Optional[str] = None, status: Optional[str] = None
    ) -> List[ActionProposal]:
        with self._lock:
            res = list(self._action_proposals.values())
            if machine_id:
                res = [p for p in res if p.machine_id == machine_id]
            if status:
                res = [p for p in res if p.status == status or (hasattr(p.status, "value") and p.status.value == status)]
            return sorted(res, key=lambda p: _safe_dt(p.created_at), reverse=True)

    def update_action_proposal(self, proposal: ActionProposal) -> ActionProposal:
        with self._lock:
            self._action_proposals[proposal.action_proposal_id] = proposal
            return proposal

    def save_action_execution(self, execution: ActionExecution) -> ActionExecution:
        with self._lock:
            if execution.idempotency_key:
                for existing in self._action_executions.values():
                    if existing.idempotency_key == execution.idempotency_key:
                        return existing
            self._action_executions[execution.execution_id] = execution
            return execution

    def get_action_execution(self, execution_id: str) -> Optional[ActionExecution]:
        with self._lock:
            return self._action_executions.get(execution_id)

    def list_action_executions(
        self, action_proposal_id: Optional[str] = None
    ) -> List[ActionExecution]:
        with self._lock:
            res = list(self._action_executions.values())
            if action_proposal_id:
                res = [e for e in res if e.action_proposal_id == action_proposal_id]
            return sorted(res, key=lambda e: _safe_dt(e.started_at), reverse=True)

    def save_action_outcome(self, outcome: ActionOutcome) -> ActionOutcome:
        with self._lock:
            self._action_outcomes[outcome.outcome_id] = outcome
            return outcome

    def get_action_outcome(self, outcome_id: str) -> Optional[ActionOutcome]:
        with self._lock:
            return self._action_outcomes.get(outcome_id)

    def list_action_outcomes(
        self, machine_id: Optional[str] = None
    ) -> List[ActionOutcome]:
        with self._lock:
            res = list(self._action_outcomes.values())
            if machine_id:
                res = [o for o in res if o.machine_id == machine_id]
            return sorted(res, key=lambda o: _safe_dt(o.recorded_at), reverse=True)

    def save_verification_policy(self, policy: VerificationPolicy) -> None:
        with self._lock:
            self._verification_policies[policy.policy_id] = policy

    def get_verification_policy(
        self, machine_id: Optional[str] = None, failure_mode: Optional[str] = None
    ) -> Optional[VerificationPolicy]:
        with self._lock:
            if machine_id:
                for pol in self._verification_policies.values():
                    if pol.machine_id == machine_id:
                        return pol
            if failure_mode:
                for pol in self._verification_policies.values():
                    if pol.failure_mode == failure_mode:
                        return pol
            return self._verification_policies.get("DEFAULT_VIB_TEMP", VerificationPolicy())

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

    def list_documents(self) -> List[Document]:
        with self._lock:
            return list(self._documents.values())

    # Canonical Prediction implementations
    def save_canonical_prediction(self, prediction: CanonicalPrediction) -> None:
        with self._lock:
            self._canonical_predictions[prediction.prediction_id] = prediction

    def get_canonical_prediction(self, prediction_id: str) -> Optional[CanonicalPrediction]:
        with self._lock:
            return self._canonical_predictions.get(prediction_id)

    def list_canonical_predictions(
        self, machine_id: Optional[str] = None, limit: int = 50
    ) -> List[CanonicalPrediction]:
        with self._lock:
            preds = list(self._canonical_predictions.values())
            if machine_id:
                preds = [p for p in preds if p.machine_id == machine_id]
            return sorted(preds, key=lambda p: p.scored_ts, reverse=True)[:limit]

    # SupplyChainRepository implementations
    def get_spare_part(self, part_id: str) -> Optional[SparePart]:
        with self._lock:
            return self._spare_parts.get(part_id)

    def list_spare_parts(
        self, category: Optional[str] = None, supplier_id: Optional[str] = None
    ) -> List[SparePart]:
        with self._lock:
            parts = list(self._spare_parts.values())
            if category:
                parts = [p for p in parts if p.part_category == category]
            if supplier_id:
                parts = [p for p in parts if p.supplier_id == supplier_id]
            return sorted(parts, key=lambda p: p.part_id)

    def get_supplier(self, supplier_id: str) -> Optional[Supplier]:
        with self._lock:
            return self._suppliers.get(supplier_id)

    def list_suppliers(self) -> List[Supplier]:
        with self._lock:
            return sorted(list(self._suppliers.values()), key=lambda s: s.supplier_id)

    def get_purchase_order(self, po_id: str) -> Optional[PurchaseOrder]:
        with self._lock:
            return self._purchase_orders.get(po_id)

    def list_purchase_orders(
        self, part_id: Optional[str] = None, supplier_id: Optional[str] = None
    ) -> List[PurchaseOrder]:
        with self._lock:
            pos = list(self._purchase_orders.values())
            if part_id:
                pos = [p for p in pos if p.part_id == part_id]
            if supplier_id:
                pos = [p for p in pos if p.supplier_id == supplier_id]
            return sorted(pos, key=lambda p: p.order_date, reverse=True)

    def get_production_order(self, order_id: str) -> Optional[ProductionOrder]:
        with self._lock:
            return self._production_orders.get(order_id)

    def list_production_orders(
        self, machine_id: Optional[str] = None, status: Optional[str] = None
    ) -> List[ProductionOrder]:
        with self._lock:
            orders = list(self._production_orders.values())
            if machine_id:
                orders = [o for o in orders if o.machine_id == machine_id]
            if status:
                orders = [o for o in orders if o.status == status]
            return sorted(orders, key=lambda o: o.due_date)

    def reserve_spare_part(self, part_id: str, qty: int = 1) -> bool:
        with self._lock:
            part = self._spare_parts.get(part_id)
            if not part:
                return False
            if part.stock_qty < qty:
                return False
            updated_part = SparePart(
                part_id=part.part_id,
                part_name=part.part_name,
                part_category=part.part_category,
                compatible_model=part.compatible_model,
                unit_cost_inr=part.unit_cost_inr,
                supplier_id=part.supplier_id,
                lead_time_days=part.lead_time_days,
                stock_qty=part.stock_qty - qty,
                reorder_level=part.reorder_level,
                reorder_qty=part.reorder_qty,
                warehouse_bin=part.warehouse_bin,
            )
            self._spare_parts[part_id] = updated_part
            return True

    # AnalyticsRepository implementations
    def get_machine_health_daily(
        self, machine_id: str, metric_date: Optional[date] = None
    ) -> Optional[MachineHealthDaily]:
        with self._lock:
            if metric_date:
                return self._health_daily.get((machine_id, metric_date))
            matches = [h for (m, _), h in self._health_daily.items() if m == machine_id]
            if matches:
                return sorted(matches, key=lambda x: x.metric_date, reverse=True)[0]
            return None

    def list_machine_health_daily(
        self, metric_date: Optional[date] = None, line_id: Optional[str] = None
    ) -> List[MachineHealthDaily]:
        with self._lock:
            res = list(self._health_daily.values())
            if metric_date:
                res = [h for h in res if h.metric_date == metric_date]
            if line_id:
                res = [h for h in res if h.line_id == line_id]
            return sorted(res, key=lambda h: (h.metric_date, h.machine_id), reverse=True)

    def get_machine_oee_daily(
        self, machine_id: str, metric_date: Optional[date] = None
    ) -> Optional[MachineOEEDaily]:
        with self._lock:
            if metric_date:
                return self._oee_daily.get((machine_id, metric_date))
            matches = [o for (m, _), o in self._oee_daily.items() if m == machine_id]
            if matches:
                return sorted(matches, key=lambda x: x.metric_date, reverse=True)[0]
            return None

    def list_machine_oee_daily(
        self, metric_date: Optional[date] = None, line_id: Optional[str] = None
    ) -> List[MachineOEEDaily]:
        with self._lock:
            res = list(self._oee_daily.values())
            if metric_date:
                res = [o for o in res if o.metric_date == metric_date]
            if line_id:
                res = [o for o in res if o.line_id == line_id]
            return sorted(res, key=lambda o: (o.metric_date, o.machine_id), reverse=True)

    def get_downtime_daily(
        self, machine_id: str, metric_date: Optional[date] = None
    ) -> Optional[DowntimeSummary]:
        with self._lock:
            if metric_date:
                return self._downtime_daily.get((machine_id, metric_date))
            matches = [d for (m, _), d in self._downtime_daily.items() if m == machine_id]
            if matches:
                return sorted(matches, key=lambda x: x.metric_date, reverse=True)[0]
            return None

    def list_downtime_daily(
        self, metric_date: Optional[date] = None
    ) -> List[DowntimeSummary]:
        with self._lock:
            res = list(self._downtime_daily.values())
            if metric_date:
                res = [d for d in res if d.metric_date == metric_date]
            return sorted(res, key=lambda d: (d.metric_date, d.machine_id), reverse=True)

    def get_maintenance_daily(
        self, machine_id: str, metric_date: Optional[date] = None
    ) -> Optional[MaintenanceSummary]:
        with self._lock:
            if metric_date:
                return self._maintenance_daily.get((machine_id, metric_date))
            matches = [m for (mid, _), m in self._maintenance_daily.items() if mid == machine_id]
            if matches:
                return sorted(matches, key=lambda x: x.metric_date, reverse=True)[0]
            return None

    def list_maintenance_daily(
        self, metric_date: Optional[date] = None
    ) -> List[MaintenanceSummary]:
        with self._lock:
            res = list(self._maintenance_daily.values())
            if metric_date:
                res = [m for m in res if m.metric_date == metric_date]
            return sorted(res, key=lambda m: (m.metric_date, m.machine_id), reverse=True)

    def get_inventory_risk(self, part_id: str) -> Optional[InventoryRisk]:
        with self._lock:
            return self._inventory_risks.get(part_id)

    def list_inventory_risks(
        self, critical_only: bool = False
    ) -> List[InventoryRisk]:
        with self._lock:
            res = list(self._inventory_risks.values())
            if critical_only:
                res = [r for r in res if r.is_critical_exposure]
            return sorted(res, key=lambda r: r.part_id)

    def get_production_context(
        self, production_order_id: str
    ) -> Optional[ProductionContext]:
        with self._lock:
            return self._production_contexts.get(production_order_id)

    def list_production_contexts(
        self, machine_id: Optional[str] = None, status: Optional[str] = None
    ) -> List[ProductionContext]:
        with self._lock:
            res = list(self._production_contexts.values())
            if machine_id:
                res = [p for p in res if p.machine_id == machine_id]
            if status:
                res = [p for p in res if p.status == status]
            return sorted(res, key=lambda p: p.due_date)

    def get_reliability_features(
        self, machine_id: str, feature_date: Optional[date] = None
    ) -> Optional[ReliabilityFeatures]:
        with self._lock:
            if feature_date:
                return self._reliability_features.get((machine_id, feature_date))
            matches = [f for (m, _), f in self._reliability_features.items() if m == machine_id]
            if matches:
                return sorted(matches, key=lambda x: x.feature_date, reverse=True)[0]
            return None

    # KnowledgeSearchRepository implementations
    def get_document(self, document_id: str) -> Optional[KnowledgeDocument]:
        with self._lock:
            return self._knowledge_documents.get(document_id)

    def list_documents(
        self, doc_type: Optional[str] = None, failure_code: Optional[str] = None
    ) -> List[KnowledgeDocument]:
        with self._lock:
            docs = list(self._knowledge_documents.values())
            if doc_type:
                docs = [d for d in docs if d.doc_type == doc_type]
            if failure_code:
                docs = [d for d in docs if d.failure_code == failure_code]
            return sorted(docs, key=lambda d: d.document_id)

    def search_corpus(
        self, query: str, limit: int = 5, failure_code: Optional[str] = None
    ) -> List[KnowledgeDocument]:
        with self._lock:
            q_lower = query.lower()
            tokens = [t for t in q_lower.replace(",", " ").replace(".", " ").split() if len(t) > 2]
            scored: List[Tuple[int, KnowledgeDocument]] = []
            for doc in self._knowledge_documents.values():
                if failure_code and doc.failure_code != failure_code:
                    continue
                score = 0
                searchable = f"{doc.title} {doc.content} {doc.component_type or ''} {doc.failure_code or ''}".lower()
                for token in tokens:
                    if token in searchable:
                        score += 1
                if score > 0:
                    scored.append((score, doc))
            scored.sort(key=lambda x: (x[0], x[1].document_id), reverse=True)
            return [d for _, d in scored[:limit]]

    def get_failure_mode(self, failure_code: str) -> Optional[FailureModeTaxonomy]:
        with self._lock:
            return self._failure_modes.get(failure_code)

    def list_failure_modes(
        self, category: Optional[str] = None
    ) -> List[FailureModeTaxonomy]:
        with self._lock:
            modes = list(self._failure_modes.values())
            if category:
                modes = [m for m in modes if m.category == category]
            return sorted(modes, key=lambda m: m.failure_code)

    # MLRepository implementations
    def save_model_metadata(self, record: ModelRegistryRecord) -> None:
        with self._lock:
            self._models[record.model_id] = record

    def get_model(self, model_id: str) -> Optional[ModelRegistryRecord]:
        with self._lock:
            return self._models.get(model_id)

    def get_active_model(self) -> Optional[ModelRegistryRecord]:
        with self._lock:
            # Active status has priority, most recently trained first
            active = [m for m in self._models.values() if m.status == "active"]
            if active:
                return sorted(active, key=lambda m: _safe_dt(m.trained_at), reverse=True)[0]
            return None

    def list_models(self, status: Optional[str] = None) -> List[ModelRegistryRecord]:
        with self._lock:
            models = list(self._models.values())
            if status:
                models = [m for m in models if m.status == status]
            return sorted(models, key=lambda m: _safe_dt(m.trained_at), reverse=True)

    def promote_model(self, model_id: str, target_status: str = "active") -> Optional[ModelRegistryRecord]:
        with self._lock:
            rec = self._models.get(model_id)
            if not rec:
                return None
            if target_status == "active":
                # Demote other active models to validated
                for m in self._models.values():
                    if m.status == "active" and m.model_id != model_id:
                        self._models[m.model_id] = m.model_copy(update={"status": "validated"})
            updated = rec.model_copy(update={"status": target_status})
            self._models[model_id] = updated
            return updated

    def save_evaluation(self, eval_record: ModelEvaluationRecord) -> None:
        with self._lock:
            if eval_record.model_id not in self._evaluations:
                self._evaluations[eval_record.model_id] = []
            self._evaluations[eval_record.model_id].append(eval_record)

    def list_evaluations(self, model_id: Optional[str] = None) -> List[ModelEvaluationRecord]:
        with self._lock:
            if model_id:
                return list(self._evaluations.get(model_id, []))
            all_evals: List[ModelEvaluationRecord] = []
            for evals in self._evaluations.values():
                all_evals.extend(evals)
            return sorted(all_evals, key=lambda e: _safe_dt(e.evaluated_at), reverse=True)

    def save_prediction_feature_snapshot(self, snapshot: PredictionFeatureSnapshot) -> None:
        with self._lock:
            self._prediction_snapshots[snapshot.snapshot_id] = snapshot

    def get_prediction_feature_snapshot(self, snapshot_id: str) -> Optional[PredictionFeatureSnapshot]:
        with self._lock:
            return self._prediction_snapshots.get(snapshot_id)

    def save_prediction_lineage(self, lineage: PredictionLineage) -> None:
        with self._lock:
            self._prediction_lineages[lineage.prediction_id] = lineage

    def get_prediction_lineage(self, prediction_id: str) -> Optional[PredictionLineage]:
        with self._lock:
            return self._prediction_lineages.get(prediction_id)

    def get_prediction_by_id(self, prediction_id: str) -> Optional[MLFailurePrediction]:
        with self._lock:
            for preds in self._predictions.values():
                for p in preds:
                    if p.prediction_id == prediction_id:
                        return p
            cp = self._canonical_predictions.get(prediction_id)
            if cp:
                return _canonical_to_ml_prediction(cp)
            return None

    def get_predictions_for_machine(self, machine_id: str, limit: int = 50) -> List[MLFailurePrediction]:
        with self._lock:
            preds = list(self._predictions.get(machine_id, []))
            preds.sort(key=lambda p: _safe_dt(p.prediction_timestamp), reverse=True)
            return preds[:limit]

