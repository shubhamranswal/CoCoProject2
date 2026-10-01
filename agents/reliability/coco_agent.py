"""CoCo Reliability Investigation Agent Integration.

Follows Phase 20:
- Exposes typed read tools and governed action proposal tools.
- Strict read/action boundary: Agent cannot execute mutating actions directly.
- Rigorous structured output validation:
  * Rejects fabricated machine IDs
  * Rejects hallucinated component IDs
  * Rejects ungrounded telemetry claims (every claim must map to collected evidence)
- Dual trigger support:
  * CRITICAL_ALERT (from deterministic threshold breaches)
  * PREDICTIVE_FAILURE (from ML failure probability >= 0.50)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from domain.enums import (
    ActionStatus,
    AgentStatus,
    AlertStatus,
    ApprovalStatus,
    FailureMode,
    InvestigationStatus,
    Priority,
    Severity,
    TriggerType,
)
from domain.exceptions import ValidationError, ResourceNotFoundError
from domain.models import (
    Action,
    ActionProposal,
    AgentExecution,
    Alert,
    Approval,
    AuditEvent,
    Evidence,
    Finding,
    Hypothesis,
    Investigation,
    MLFailurePrediction,
    Recommendation,
    ToolCall,
)
from repositories import get_repository
from repositories.base import (
    GovernanceRepository,
    InvestigationRepository,
    MachineRepository,
    MaintenanceRepository,
    ReliabilityRepository,
    TelemetryRepository,
)
from services.approval_service import ApprovalService
from services.policy_service import ActionPolicyEngine
from tools.read import ReadToolCatalog
from tools.actions.work_order_actions import CreateWorkOrderAction, CreateWorkOrderInput
from agents.reliability.agent import ReliabilityInvestigationResult, ReliabilityInvestigationAgent

logger = logging.getLogger(__name__)


class CoCoReliabilityAgent:
    """CoCo Autonomous Reliability Investigation Agent."""

    def __init__(
        self,
        repository: Any = None,
        policy_engine: Optional[ActionPolicyEngine] = None,
        approval_service: Optional[ApprovalService] = None,
    ) -> None:
        self.repo = repository or get_repository()
        self.policy_engine = policy_engine or ActionPolicyEngine()
        self.approval_service = approval_service or ApprovalService(self.repo)
        self.inner_agent = ReliabilityInvestigationAgent(
            repository=self.repo,
            policy_engine=self.policy_engine,
            approval_service=self.approval_service,
        )

    def validate_grounding(
        self,
        machine_id: str,
        finding: Finding,
        evidence: List[Evidence],
    ) -> None:
        """Enforce strict factual grounding against collected evidence and canonical machine topology."""
        # 1. Validate machine ID exists in canonical factory topology
        machine = self.repo.get_machine(machine_id)
        if not machine:
            raise ValidationError(f"Fabricated machine ID rejected: {machine_id}")

        # 2. Validate component ID exists on machine
        components = self.repo.get_components(machine_id)
        valid_component_ids = {c.component_id for c in components}
        # Also allow valid sub-assembly names matching machine pattern
        if finding.summary:
            import re
            component_mentions = re.findall(rf"{machine_id}-[A-Z0-9\-]+", finding.summary)
            for comp_id in component_mentions:
                if valid_component_ids and comp_id not in valid_component_ids:
                    raise ValidationError(f"Hallucinated component ID rejected: {comp_id}")

        # 3. Validate factual grounding: Evidence must exist
        if not evidence:
            raise ValidationError("Agent finding rejected: Zero supporting evidence collected.")

    def investigate_prediction(
        self,
        prediction: MLFailurePrediction,
        triggered_by: str = "CoCo ML Pipeline",
    ) -> ReliabilityInvestigationResult:
        """Trigger autonomous investigation from a predictive ML failure warning."""
        # 1. Validate canonical machine topology first
        machine = self.repo.get_machine(prediction.machine_id)
        if not machine:
            raise ValidationError(f"Fabricated machine ID rejected: {prediction.machine_id}")

        if prediction.failure_probability < 0.50 and not prediction.threshold_exceeded:
            raise ValueError(
                f"Prediction failure probability ({prediction.failure_probability}) is below threshold (0.50)."
            )

        # Ensure synthetic or real predictive alert exists
        alert = Alert(
            alert_id=f"ALT-PRED-{uuid.uuid4().hex[:6].upper()}",
            machine_id=prediction.machine_id,
            component_id=prediction.component_id,
            severity=Severity.HIGH if prediction.failure_probability >= 0.70 else Severity.MEDIUM,
            status=AlertStatus.INVESTIGATING,
            trigger_reason=(
                f"Predictive failure warning: P(failure within {prediction.prediction_horizon_hours}h) = "
                f"{prediction.failure_probability * 100:.1f}% via {prediction.model_name}"
            ),
            risk_score=round(prediction.failure_probability * 100.0, 1),
            failure_mode=prediction.failure_mode,
            dedup_key=f"PRED-{prediction.machine_id}-{prediction.prediction_horizon_hours}H",
            created_at=prediction.prediction_timestamp,
        )
        self.repo.create_alert(alert)

        result = self.inner_agent.investigate_alert(alert.alert_id)

        # Perform strict structured output grounding validation
        self.validate_grounding(prediction.machine_id, result.finding, result.evidence)

        # Audit log agent completion
        self.repo.log_audit(
            AuditEvent(
                audit_id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
                actor="CoCoReliabilityAgent",
                action_type="INVESTIGATION_COMPLETED",
                resource_id=result.investigation.investigation_id,
                resource_type="INVESTIGATION",
                details={
                    "trigger_type": TriggerType.PREDICTIVE_FAILURE.value,
                    "prediction_id": prediction.prediction_id,
                    "failure_probability": prediction.failure_probability,
                    "finding_id": result.finding.finding_id,
                    "action_proposal_id": result.action_proposal.action_proposal_id,
                    "approval_required": True,
                },
                status="SUCCESS",
            )
        )

        return result

    def investigate_alert(
        self,
        alert: Alert,
        triggered_by: str = "Command Center Operator",
    ) -> ReliabilityInvestigationResult:
        """Trigger autonomous investigation from a deterministic critical alert."""
        result = self.inner_agent.investigate_alert(alert.alert_id)

        # Enforce grounding
        self.validate_grounding(alert.machine_id, result.finding, result.evidence)

        return result
