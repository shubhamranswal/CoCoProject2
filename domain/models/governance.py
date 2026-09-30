"""Governance, Policy, Approval, Action, Verification, and Audit domain models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from domain.enums import ActionStatus, ApprovalStatus


class Action(BaseModel):
    action_id: str
    recommendation_id: str
    action_type: str  # CREATE_WORK_ORDER, ESCALATE, NOTIFY
    payload: Dict[str, Any]
    status: ActionStatus = ActionStatus.PROPOSED
    requires_approval: bool = True
    executed_at: Optional[datetime] = None


class Approval(BaseModel):
    approval_id: str
    action_id: str
    investigation_id: str
    machine_id: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_by: str = "ReliabilityAgent"
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    decision_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


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
    is_recovered: bool
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
