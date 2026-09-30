"""Intelligence domain models: Alert, Investigation, Evidence, Hypothesis, Finding, Recommendation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from domain.enums import AlertStatus, FailureMode, InvestigationStatus, Priority, Severity


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
    evidence_type: str  # TELEMETRY, ANOMALY, RISK, MAINTENANCE, FAILURE_HISTORY, PRODUCTION, OEE, DOCUMENT
    source: str
    metric: str
    observed_value: Any
    baseline_value: Optional[Any] = None
    relationship: str = "SUPPORTS"  # SUPPORTS, CONTRADICTS, CONTEXTUAL, CORRELATES
    machine_id: Optional[str] = None
    component_id: Optional[str] = None
    observed_fact: Optional[str] = None
    is_contradictory: bool = False
    summary: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Hypothesis(BaseModel):
    hypothesis_id: str
    investigation_id: str
    hypothesis_name: str
    failure_mode: FailureMode
    confidence: float = Field(..., ge=0.0, le=1.0)
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    contradicting_evidence_ids: List[str] = Field(default_factory=list)
    status: str = "EVALUATED"  # SUPPORTED, REFUTED, INCONCLUSIVE
    rationale: str


class Finding(BaseModel):
    finding_id: str
    investigation_id: str
    summary: str
    failure_mode: FailureMode
    confidence: float = Field(..., ge=0.0, le=1.0)
    observed_facts: List[str] = Field(default_factory=list)
    historical_facts: List[str] = Field(default_factory=list)
    inferences: List[str] = Field(default_factory=list)
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    contradicting_evidence_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Recommendation(BaseModel):
    recommendation_id: str
    investigation_id: str
    title: str
    action_type: str = "INSPECT_BEARING_ASSEMBLY"
    action_description: str
    priority: Priority
    action_required: bool = True
    estimated_downtime_hours: float = 2.0
    suggested_parts: List[str] = Field(default_factory=list)
    suggested_checklist: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)


class ActionProposal(BaseModel):
    action_proposal_id: str
    investigation_id: str
    action_type: str  # INSPECT_BEARING_ASSEMBLY, CREATE_WORK_ORDER
    machine_id: str
    component_id: Optional[str] = None
    priority: Priority = Priority.HIGH
    reason: str
    recommendation_id: str
    evidence_ids: List[str] = Field(default_factory=list)
    risk_level: str = "HIGH"
    requires_approval: bool = True
    approval_id: Optional[str] = None


class Investigation(BaseModel):
    investigation_id: str
    alert_id: Optional[str] = None
    machine_id: str
    status: InvestigationStatus = InvestigationStatus.CREATED
    failure_mode: FailureMode = FailureMode.BEARING_DEGRADATION
    confidence: float = 0.0
    finding: Optional[Finding] = None
    recommendation: Optional[Recommendation] = None
    action_proposal: Optional[ActionProposal] = None
    evidence: List[Evidence] = Field(default_factory=list)
    hypotheses: List[Hypothesis] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    summary: Optional[str] = None

