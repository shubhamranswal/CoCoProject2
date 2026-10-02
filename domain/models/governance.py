"""Governance, Policy, Approval, Action, Verification, and Audit domain models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from domain.enums import ActionStatus, ApprovalStatus, VerificationStatus


class Action(BaseModel):
    action_id: str
    recommendation_id: str
    action_type: str  # CREATE_WORK_ORDER, ESCALATE, NOTIFY, INSPECT_BEARING_ASSEMBLY, RESERVE_SPARE_PART, ASSIGN_TECHNICIAN
    payload: Dict[str, Any]
    status: ActionStatus = ActionStatus.PROPOSED
    requires_approval: bool = True
    executed_at: Optional[datetime] = None


class Approval(BaseModel):
    approval_id: str
    action_id: Optional[str] = None
    investigation_id: str
    machine_id: str
    recommendation_id: Optional[str] = None
    action_proposal_id: Optional[str] = None
    requested_action: Optional[str] = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_by: str = "ReliabilityAgent"
    decision_by: Optional[str] = None
    decision_at: Optional[datetime] = None
    decision_reason: Optional[str] = None
    reviewed_by: Optional[str] = None  # Alias for decision_by
    reviewed_at: Optional[datetime] = None  # Alias for decision_at
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    authorization_context: Dict[str, Any] = Field(default_factory=dict)


class ActionExecution(BaseModel):
    execution_id: str
    action_proposal_id: str
    approval_id: str
    action_type: str
    machine_id: str
    executed_by: str = "SYSTEM"
    status: str = "SUCCESS"  # SUCCESS, FAILED
    idempotency_key: Optional[str] = None
    result_data: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None


class VerificationPolicy(BaseModel):
    policy_id: str = "DEFAULT_VIB_TEMP"
    machine_id: Optional[str] = None
    failure_mode: Optional[str] = None
    max_acceptable_vibration_rms: float = 0.50
    max_acceptable_temperature: float = 65.0
    max_acceptable_risk_score: float = 0.25
    min_vibration_reduction_pct: float = 30.0
    min_risk_reduction_pct: float = 50.0
    require_zero_active_critical_anomalies: bool = True
    min_oee_target: float = 0.75
    baseline_window_hours: int = 24
    verification_window_hours: int = 24


class Verification(BaseModel):
    verification_id: str
    investigation_id: str
    work_order_id: str
    machine_id: str
    action_execution_id: Optional[str] = None
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pre_vibration_rms: Optional[float] = None
    post_vibration_rms: Optional[float] = None
    pre_temperature_c: Optional[float] = None
    post_temperature_c: Optional[float] = None
    pre_risk_score: Optional[float] = None
    post_risk_score: Optional[float] = None
    risk_delta: float = 0.0
    pre_oee: float = 0.0
    post_oee: float = 0.0
    oee_delta: float = 0.0
    anomalies_before: int = 0
    anomalies_after: int = 0
    is_recovered: bool = False
    verification_status: VerificationStatus = VerificationStatus.VERIFIED
    verification_reason: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    oee_recovery_pct: float = 0.0
    evaluated_by: str = "SYSTEM"
    notes: str = ""


# Alias for explicit naming
VerificationResult = Verification


class ActionOutcome(BaseModel):
    """Closed-loop learning model capturing maintenance and prediction outcomes."""
    outcome_id: str
    action_proposal_id: str
    work_order_id: str
    execution_id: Optional[str] = None
    verification_id: Optional[str] = None
    prediction_id: Optional[str] = None
    machine_id: str
    failure_mode: str = "BEARING_DEGRADATION"
    observed_failure_confirmed: bool = True
    downtime_avoided_hours: float = 0.0
    verification_status: VerificationStatus = VerificationStatus.VERIFIED
    feedback_notes: str = ""
    telemetry_provenance: Dict[str, Any] = Field(default_factory=dict)
    is_simulated_telemetry: bool = False
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditEvent(BaseModel):
    audit_id: str
    actor: str  # user or agent name
    action_type: str
    resource_id: str
    resource_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = Field(default_factory=dict)
    status: str = "SUCCESS"
