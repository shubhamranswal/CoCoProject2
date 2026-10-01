"""Repository abstractions separating business logic from storage implementation.

Follows AGENT.md:
- Clear separation between Snowflake and in-memory test implementation
- Domain layer remains agnostic of underlying physical storage
"""

from __future__ import annotations

from abc import ABC, abstractmethod
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
    WorkOrder,
    Document,
    MLFailurePrediction,
    PredictionOutcome,
    CanonicalPrediction,
    Product,
    ProductionOrder,
    PurchaseOrder,
    SparePart,
    Supplier,
    WorkOrderPartUsage,
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

