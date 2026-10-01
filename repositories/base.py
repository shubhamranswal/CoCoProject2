"""Repository abstractions separating business logic from storage implementation.

Follows AGENT.md:
- Clear separation between Snowflake and in-memory test implementation
- Domain layer remains agnostic of underlying physical storage
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import List, Optional

from domain.enums import AlertStatus, ApprovalStatus, HealthStatus, MachineState, WorkOrderStatus
from domain.models import (
    Alert,
    Anomaly,
    Approval,
    AuditEvent,
    Baseline,
    Component,
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
    VerificationResult,
    VerificationPolicy,
    ActionProposal,
    ActionExecution,
    ActionOutcome,
    WorkOrder,
    Document,
    KnowledgeDocument,
    FailureModeTaxonomy,
    MLFailurePrediction,
    PredictionOutcome,
    CanonicalPrediction,
    ModelRegistryRecord,
    ModelEvaluationRecord,
    PredictionFeatureSnapshot,
    PredictionLineage,
    Product,
    ProductionOrder,
    PurchaseOrder,
    SparePart,
    Supplier,
    WorkOrderPartUsage,
    MachineHealthDaily,
    MachineOEEDaily,
    DowntimeSummary,
    MaintenanceSummary,
    InventoryRisk,
    ProductionContext,
    ReliabilityFeatures,
)


class MachineRepository(ABC):
    @abstractmethod
    def get_plant(self, plant_id: str) -> Optional[Plant]: ...

    @abstractmethod
    def list_lines(self, plant_id: str) -> List[ProductionLine]: ...

    @abstractmethod
    def get_machine(self, machine_id: str) -> Optional[Machine]: ...

    @abstractmethod
    def list_machines(self, line_id: Optional[str] = None) -> List[Machine]: ...

    @abstractmethod
    def get_components(self, machine_id: str) -> List[Component]: ...

    @abstractmethod
    def get_sensors(self, machine_id: str) -> List[Sensor]: ...

    @abstractmethod
    def update_machine_health(
        self, machine_id: str, health_status: HealthStatus, state: Optional[MachineState] = None
    ) -> Machine: ...


class TelemetryRepository(ABC):
    @abstractmethod
    def save_measurements(self, measurements: List[TelemetryMeasurement]) -> None: ...

    @abstractmethod
    def get_recent_measurements(
        self, machine_id: str, sensor_id: Optional[str] = None, limit: int = 100
    ) -> List[TelemetryMeasurement]: ...

    @abstractmethod
    def save_feature(self, feature: FeatureVector) -> None: ...

    @abstractmethod
    def get_latest_features(self, machine_id: str) -> Optional[FeatureVector]: ...

    @abstractmethod
    def get_baseline(self, machine_id: str, signal_name: str) -> Optional[Baseline]: ...

    @abstractmethod
    def save_anomaly(self, anomaly: Anomaly) -> None: ...

    @abstractmethod
    def get_anomalies(self, machine_id: str, active_only: bool = True) -> List[Anomaly]: ...

    @abstractmethod
    def list_anomalies(self, machine_id: Optional[str] = None, active_only: bool = True) -> List[Anomaly]: ...


class MaintenanceRepository(ABC):
    @abstractmethod
    def get_maintenance_history(self, machine_id: str, limit: int = 20) -> List[MaintenanceEvent]: ...

    @abstractmethod
    def save_maintenance_event(self, event: MaintenanceEvent) -> None: ...

    @abstractmethod
    def create_work_order(self, work_order: WorkOrder) -> WorkOrder: ...

    @abstractmethod
    def get_work_order(self, work_order_id: str) -> Optional[WorkOrder]: ...

    @abstractmethod
    def list_work_orders(
        self, machine_id: Optional[str] = None, status: Optional[WorkOrderStatus] = None
    ) -> List[WorkOrder]: ...

    @abstractmethod
    def update_work_order_status(self, work_order_id: str, status: WorkOrderStatus) -> WorkOrder: ...

    @abstractmethod
    def update_work_order(self, work_order: WorkOrder) -> WorkOrder: ...


class ReliabilityRepository(ABC):
    @abstractmethod
    def get_failure_history(self, machine_id: str) -> List[Failure]: ...

    @abstractmethod
    def save_failure_risk(self, risk: FailureRisk) -> None: ...

    @abstractmethod
    def get_latest_failure_risk(self, machine_id: str) -> Optional[FailureRisk]: ...

    @abstractmethod
    def save_health_assessment(self, assessment: HealthAssessment) -> None: ...

    @abstractmethod
    def get_latest_health_assessment(self, machine_id: str) -> Optional[HealthAssessment]: ...

    @abstractmethod
    def save_prediction(self, prediction: MLFailurePrediction) -> None: ...

    @abstractmethod
    def get_latest_prediction(self, machine_id: str) -> Optional[MLFailurePrediction]: ...

    @abstractmethod
    def list_predictions(
        self, machine_id: Optional[str] = None, limit: int = 50
    ) -> List[MLFailurePrediction]: ...

    @abstractmethod
    def save_prediction_outcome(self, outcome: PredictionOutcome) -> None: ...

    @abstractmethod
    def get_prediction_outcome(self, prediction_id: str) -> Optional[PredictionOutcome]: ...

    @abstractmethod
    def list_prediction_outcomes(
        self, machine_id: Optional[str] = None
    ) -> List[PredictionOutcome]: ...

    @abstractmethod
    def save_canonical_prediction(self, prediction: CanonicalPrediction) -> None: ...

    @abstractmethod
    def get_canonical_prediction(self, prediction_id: str) -> Optional[CanonicalPrediction]: ...

    @abstractmethod
    def list_canonical_predictions(
        self, machine_id: Optional[str] = None, limit: int = 50
    ) -> List[CanonicalPrediction]: ...


class InvestigationRepository(ABC):
    @abstractmethod
    def create_alert(self, alert: Alert) -> Alert: ...

    @abstractmethod
    def get_alert(self, alert_id: str) -> Optional[Alert]: ...

    @abstractmethod
    def list_alerts(
        self, machine_id: Optional[str] = None, status: Optional[AlertStatus] = None
    ) -> List[Alert]: ...

    @abstractmethod
    def create_investigation(self, investigation: Investigation) -> Investigation: ...

    @abstractmethod
    def get_investigation(self, investigation_id: str) -> Optional[Investigation]: ...

    @abstractmethod
    def save_evidence(self, evidence: List[Evidence]) -> None: ...

    @abstractmethod
    def get_evidence(self, investigation_id: str) -> List[Evidence]: ...

    @abstractmethod
    def update_investigation(self, investigation: Investigation) -> Investigation: ...

    @abstractmethod
    def list_investigations(self, machine_id: Optional[str] = None) -> List[Investigation]: ...

    @abstractmethod
    def get_investigation_by_alert(self, alert_id: str) -> Optional[Investigation]: ...


class GovernanceRepository(ABC):
    @abstractmethod
    def create_approval(self, approval: Approval) -> Approval: ...

    @abstractmethod
    def get_approval(self, approval_id: str) -> Optional[Approval]: ...

    @abstractmethod
    def list_approvals(
        self, machine_id: Optional[str] = None, status: Optional[ApprovalStatus] = None
    ) -> List[Approval]: ...

    @abstractmethod
    def update_approval(
        self, approval_id: str, status: ApprovalStatus, reviewer: str, reason: str
    ) -> Approval: ...

    @abstractmethod
    def save_verification(self, verification: Verification) -> None: ...

    @abstractmethod
    def get_verification(self, work_order_id: str) -> Optional[Verification]: ...

    @abstractmethod
    def get_verification_by_investigation(self, investigation_id: str) -> Optional[Verification]: ...

    @abstractmethod
    def list_verifications(self, machine_id: Optional[str] = None) -> List[Verification]: ...

    @abstractmethod
    def log_audit(self, event: AuditEvent) -> None: ...

    @abstractmethod
    def list_audit_events(self, limit: int = 50) -> List[AuditEvent]: ...

    @abstractmethod
    def save_action_proposal(self, proposal: ActionProposal) -> ActionProposal: ...

    @abstractmethod
    def get_action_proposal(self, action_proposal_id: str) -> Optional[ActionProposal]: ...

    @abstractmethod
    def list_action_proposals(
        self, machine_id: Optional[str] = None, status: Optional[str] = None
    ) -> List[ActionProposal]: ...

    @abstractmethod
    def update_action_proposal(self, proposal: ActionProposal) -> ActionProposal: ...

    @abstractmethod
    def save_action_execution(self, execution: ActionExecution) -> ActionExecution: ...

    @abstractmethod
    def get_action_execution(self, execution_id: str) -> Optional[ActionExecution]: ...

    @abstractmethod
    def list_action_executions(
        self, action_proposal_id: Optional[str] = None
    ) -> List[ActionExecution]: ...

    @abstractmethod
    def save_action_outcome(self, outcome: ActionOutcome) -> ActionOutcome: ...

    @abstractmethod
    def get_action_outcome(self, outcome_id: str) -> Optional[ActionOutcome]: ...

    @abstractmethod
    def list_action_outcomes(
        self, machine_id: Optional[str] = None
    ) -> List[ActionOutcome]: ...

    @abstractmethod
    def save_verification_policy(self, policy: VerificationPolicy) -> None: ...

    @abstractmethod
    def get_verification_policy(
        self, machine_id: Optional[str] = None, failure_mode: Optional[str] = None
    ) -> Optional[VerificationPolicy]: ...


class KnowledgeRepository(ABC):
    @abstractmethod
    def get_manual(self, machine_model: str) -> Optional[Document]: ...

    @abstractmethod
    def search_docs(self, query: str) -> List[str]: ...

    @abstractmethod
    def list_documents(self) -> List[Document]: ...


class SupplyChainRepository(ABC):
    """Canonical factory repository for materials, suppliers, and customer orders."""

    @abstractmethod
    def get_spare_part(self, part_id: str) -> Optional[SparePart]: ...

    @abstractmethod
    def list_spare_parts(
        self, category: Optional[str] = None, supplier_id: Optional[str] = None
    ) -> List[SparePart]: ...

    @abstractmethod
    def get_supplier(self, supplier_id: str) -> Optional[Supplier]: ...

    @abstractmethod
    def list_suppliers(self) -> List[Supplier]: ...

    @abstractmethod
    def get_purchase_order(self, po_id: str) -> Optional[PurchaseOrder]: ...

    @abstractmethod
    def list_purchase_orders(
        self, part_id: Optional[str] = None, supplier_id: Optional[str] = None
    ) -> List[PurchaseOrder]: ...

    @abstractmethod
    def get_production_order(self, order_id: str) -> Optional[ProductionOrder]: ...

    @abstractmethod
    def list_production_orders(
        self, machine_id: Optional[str] = None, status: Optional[str] = None
    ) -> List[ProductionOrder]: ...

    @abstractmethod
    def reserve_spare_part(self, part_id: str, qty: int = 1) -> bool: ...


class AnalyticsRepository(ABC):
    """Canonical factory repository for analytical views and operational KPIs."""

    @abstractmethod
    def get_machine_health_daily(
        self, machine_id: str, metric_date: Optional[date] = None
    ) -> Optional[MachineHealthDaily]: ...

    @abstractmethod
    def list_machine_health_daily(
        self, metric_date: Optional[date] = None, line_id: Optional[str] = None
    ) -> List[MachineHealthDaily]: ...

    @abstractmethod
    def get_machine_oee_daily(
        self, machine_id: str, metric_date: Optional[date] = None
    ) -> Optional[MachineOEEDaily]: ...

    @abstractmethod
    def list_machine_oee_daily(
        self, metric_date: Optional[date] = None, line_id: Optional[str] = None
    ) -> List[MachineOEEDaily]: ...

    @abstractmethod
    def get_downtime_daily(
        self, machine_id: str, metric_date: Optional[date] = None
    ) -> Optional[DowntimeSummary]: ...

    @abstractmethod
    def list_downtime_daily(
        self, metric_date: Optional[date] = None
    ) -> List[DowntimeSummary]: ...

    @abstractmethod
    def get_maintenance_daily(
        self, machine_id: str, metric_date: Optional[date] = None
    ) -> Optional[MaintenanceSummary]: ...

    @abstractmethod
    def list_maintenance_daily(
        self, metric_date: Optional[date] = None
    ) -> List[MaintenanceSummary]: ...

    @abstractmethod
    def get_inventory_risk(self, part_id: str) -> Optional[InventoryRisk]: ...

    @abstractmethod
    def list_inventory_risks(
        self, critical_only: bool = False
    ) -> List[InventoryRisk]: ...

    @abstractmethod
    def get_production_context(
        self, production_order_id: str
    ) -> Optional[ProductionContext]: ...

    @abstractmethod
    def list_production_contexts(
        self, machine_id: Optional[str] = None, status: Optional[str] = None
    ) -> List[ProductionContext]: ...

    @abstractmethod
    def get_reliability_features(
        self, machine_id: str, feature_date: Optional[date] = None
    ) -> Optional[ReliabilityFeatures]: ...


class KnowledgeSearchRepository(ABC):
    """Canonical factory repository for failure mode taxonomy and corpus search."""

    @abstractmethod
    def get_document(self, document_id: str) -> Optional[KnowledgeDocument]: ...

    @abstractmethod
    def list_documents(
        self, doc_type: Optional[str] = None, failure_code: Optional[str] = None
    ) -> List[KnowledgeDocument]: ...

    @abstractmethod
    def search_corpus(
        self, query: str, limit: int = 5, failure_code: Optional[str] = None
    ) -> List[KnowledgeDocument]: ...

    @abstractmethod
    def get_failure_mode(self, failure_code: str) -> Optional[FailureModeTaxonomy]: ...

    @abstractmethod
    def list_failure_modes(
        self, category: Optional[str] = None
    ) -> List[FailureModeTaxonomy]: ...


class MLRepository(ABC):
    """Predictive production layer repository for models, evaluations, feature snapshots, and lineage."""

    @abstractmethod
    def save_model_metadata(self, record: ModelRegistryRecord) -> None: ...

    @abstractmethod
    def get_model(self, model_id: str) -> Optional[ModelRegistryRecord]: ...

    @abstractmethod
    def get_active_model(self) -> Optional[ModelRegistryRecord]: ...

    @abstractmethod
    def list_models(self, status: Optional[str] = None) -> List[ModelRegistryRecord]: ...

    @abstractmethod
    def promote_model(self, model_id: str, target_status: str = "active") -> Optional[ModelRegistryRecord]: ...

    @abstractmethod
    def save_evaluation(self, eval_record: ModelEvaluationRecord) -> None: ...

    @abstractmethod
    def list_evaluations(self, model_id: Optional[str] = None) -> List[ModelEvaluationRecord]: ...

    @abstractmethod
    def save_prediction_feature_snapshot(self, snapshot: PredictionFeatureSnapshot) -> None: ...

    @abstractmethod
    def get_prediction_feature_snapshot(self, snapshot_id: str) -> Optional[PredictionFeatureSnapshot]: ...

    @abstractmethod
    def save_prediction_lineage(self, lineage: PredictionLineage) -> None: ...

    @abstractmethod
    def get_prediction_lineage(self, prediction_id: str) -> Optional[PredictionLineage]: ...

    @abstractmethod
    def save_prediction(self, prediction: MLFailurePrediction) -> None: ...

    @abstractmethod
    def get_prediction_by_id(self, prediction_id: str) -> Optional[MLFailurePrediction]: ...

    @abstractmethod
    def get_predictions_for_machine(self, machine_id: str, limit: int = 50) -> List[MLFailurePrediction]: ...

