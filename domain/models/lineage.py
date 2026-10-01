"""End-to-end data lineage domain models for governed reliability decisions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class DecisionLineage(BaseModel):
    """End-to-end audit lineage linking raw physical telemetry to final closed-loop verification."""

    lineage_id: str
    machine_id: str
    sensor_id: Optional[str] = None
    telemetry_timestamps: List[datetime] = Field(default_factory=list)
    feature_id: Optional[str] = None
    anomaly_ids: List[str] = Field(default_factory=list)
    risk_id: Optional[str] = None
    prediction_id: Optional[str] = None
    alert_id: Optional[str] = None
    investigation_id: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)
    hypothesis_ids: List[str] = Field(default_factory=list)
    finding_id: Optional[str] = None
    recommendation_id: Optional[str] = None
    approval_id: Optional[str] = None
    work_order_id: Optional[str] = None
    maintenance_id: Optional[str] = None
    verification_id: Optional[str] = None
    outcome_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_audit_dict(self) -> Dict[str, Optional[str]]:
        return {
            "machine_id": self.machine_id,
            "sensor_id": self.sensor_id,
            "feature_id": self.feature_id,
            "prediction_id": self.prediction_id,
            "alert_id": self.alert_id,
            "investigation_id": self.investigation_id,
            "approval_id": self.approval_id,
            "work_order_id": self.work_order_id,
            "verification_id": self.verification_id,
            "outcome_id": self.outcome_id,
        }
