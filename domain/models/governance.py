"""Governance, Policy, Approval, Action, Verification, and Audit domain models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from domain.enums import ActionStatus, ApprovalStatus, VerificationStatus


class Action(BaseModel):
    action_id: str
    recommendation_id: str
    action_type: str  # CREATE_WORK_ORDER, ESCALATE, NOTIFY, INSPECT_BEARING_ASSEMBLY
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


class Verification(BaseModel):
    verification_id: str
    investigation_id: str
    work_order_id: str
    machine_id: str
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pre_vibration_rms: float
    post_vibration_rms: float
    pre_temperature_c: float
    post_temperature_c: float
    pre_risk_score: float
    post_risk_score: float
    risk_delta: float = 0.0
    pre_oee: float = 0.0
    post_oee: float = 0.0
    oee_delta: float = 0.0
    anomalies_before: int = 0
    anomalies_after: int = 0
    is_recovered: bool = True
    verification_status: VerificationStatus = VerificationStatus.VERIFIED
    verification_reason: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    oee_recovery_pct: float = 0.0
    notes: str = ""



class AuditEvent(BaseModel):
    audit_id: str
    actor: str  # user or agent name
    action_type: str
    resource_id: str
    resource_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = Field(default_factory=dict)
    status: str = "SUCCESS"
