"""Intelligence domain models: Alert, Investigation, Evidence, Hypothesis, Finding, Recommendation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from domain.enums import AlertStatus, FailureMode, InvestigationStatus, Priority, Severity, TriggerType


class Alert(BaseModel):
    alert_id: str
    machine_id: str
    component_id: Optional[str] = None
    severity: Severity
    status: AlertStatus = AlertStatus.OPEN
    trigger_reason: str
    risk_score: float
    failure_mode: FailureMode = FailureMode.BEARING_DEGRADATION
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    dedup_key: Optional[str] = None


class Evidence(BaseModel):
    evidence_id: str
    investigation_id: str
    evidence_type: str = "TELEMETRY"  # TELEMETRY, ANOMALY, RISK, MAINTENANCE, FAILURE_HISTORY, PRODUCTION, OEE, DOCUMENT, INVENTORY
    category: Optional[str] = None  # Canonical alias: PREDICTION, SENSOR, MAINTENANCE, etc.
    source: str = ""
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    metric: str = ""
    claim: Optional[str] = None
    observed_value: Any = None
    unit: Optional[str] = None
    severity: Optional[str] = None
    baseline_value: Optional[Any] = None
    relationship: str = "SUPPORTS"  # SUPPORTS, CONTRADICTS, CONTEXTUAL, CORRELATES
    machine_id: Optional[str] = None
    component_id: Optional[str] = None
    source_reference: Optional[str] = None
    timestamp_start: Optional[datetime] = None
    timestamp_end: Optional[datetime] = None
    observed_fact: Optional[str] = None
    is_contradictory: bool = False
    summary: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ToolEvidence(BaseModel):
    evidence_id: str
    tool_name: str
    source_type: str
    source_id: str
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: Dict[str, Any] = Field(default_factory=dict)


class Hypothesis(BaseModel):
    hypothesis_id: str
    investigation_id: str
    hypothesis_name: str = ""
    statement: Optional[str] = None
    failure_mode: FailureMode = FailureMode.BEARING_DEGRADATION
    confidence: float = Field(default=0.80, ge=0.0, le=1.0)
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    contradicting_evidence_ids: List[str] = Field(default_factory=list)
    status: str = "EVALUATED"  # SUPPORTED, REFUTED, INCONCLUSIVE
    rationale: str = ""


class Finding(BaseModel):
    finding_id: str
    investigation_id: str
    summary: str = ""
    statement: Optional[str] = None
    failure_mode: FailureMode = FailureMode.BEARING_DEGRADATION
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    evidence_refs: List[str] = Field(default_factory=list)
    observed_facts: List[str] = Field(default_factory=list)
    historical_facts: List[str] = Field(default_factory=list)
    inferences: List[str] = Field(default_factory=list)
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    contradicting_evidence_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Recommendation(BaseModel):
    recommendation_id: str
    investigation_id: str
    title: str = ""
    statement: Optional[str] = None
    action_type: str = "INSPECT_BEARING_ASSEMBLY"
    action_description: str = ""
    priority: Priority = Priority.HIGH
    rationale: str = ""
    suggested_next_step: Optional[str] = None
    action_required: bool = True
    status: str = "ADVISORY"  # Strictly ADVISORY in Milestone 4
    estimated_downtime_hours: float = 2.0
    suggested_parts: List[str] = Field(default_factory=list)
    suggested_checklist: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)


class ActionProposal(BaseModel):
    action_proposal_id: str
    investigation_id: str
    action_type: str  # INSPECT_BEARING_ASSEMBLY, CREATE_WORK_ORDER, RESERVE_SPARE_PART, ASSIGN_TECHNICIAN
    machine_id: str
    component_id: Optional[str] = None
    priority: Priority = Priority.HIGH
    reason: str
    recommendation_id: str = "REC-ADVISORY"
    evidence_ids: List[str] = Field(default_factory=list)
    risk_level: str = "HIGH"
    requires_approval: bool = True
    approval_id: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    status: str = "PROPOSED"  # Matches ActionProposalStatus (e.g. PROPOSED, PENDING_APPROVAL, APPROVED, etc.)
    idempotency_key: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None

    def __init__(self, **data: Any) -> None:
        if "proposal_id" in data and "action_proposal_id" not in data:
            data["action_proposal_id"] = data["proposal_id"]
        super().__init__(**data)

    @property
    def proposal_id(self) -> str:
        return self.action_proposal_id


class InvestigationRequest(BaseModel):
    request_id: str
    investigation_id: str
    trigger_type: TriggerType
    trigger_id: Optional[str] = None
    prediction_id: Optional[str] = None
    machine_id: str
    requested_by: str = "SYSTEM"
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    scope: Optional[str] = None
    user_query: Optional[str] = None


class Investigation(BaseModel):
    investigation_id: str
    trigger_type: Optional[TriggerType] = None
    trigger_id: Optional[str] = None
    prediction_id: Optional[str] = None
    alert_id: Optional[str] = None
    machine_id: str
    component_id: Optional[str] = None
    scope: Optional[str] = None
    status: InvestigationStatus = InvestigationStatus.CREATED
    failure_mode: FailureMode = FailureMode.BEARING_DEGRADATION
    confidence: float = 0.0
    finding: Optional[Finding] = None
    findings: List[Finding] = Field(default_factory=list)
    recommendation: Optional[Recommendation] = None
    recommendations: List[Recommendation] = Field(default_factory=list)
    action_proposal: Optional[ActionProposal] = None
    evidence: List[Evidence] = Field(default_factory=list)
    hypotheses: List[Hypothesis] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    summary: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class InvestigationResult(BaseModel):
    investigation_id: str
    machine_id: str
    prediction_id: Optional[str] = None
    summary: str
    hypotheses: List[Hypothesis] = Field(default_factory=list)
    findings: List[Finding] = Field(default_factory=list)
    recommendations: List[Recommendation] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    status: InvestigationStatus = InvestigationStatus.COMPLETED
