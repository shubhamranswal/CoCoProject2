"""Governed Human Approval Gateway.

Follows Milestone 5 Zero-Trust Architecture:
- Explicit Human-in-the-Loop boundary: autonomous agents strictly barred from self-approval
- Proposals transition: PROPOSED -> PENDING_APPROVAL -> APPROVED / REJECTED
- Strict validation of approver identity
- Expiration checks
- Idempotent approval calls
- Governance audit trail integration
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from domain.enums import ActionProposalStatus, ApprovalStatus
from domain.exceptions import ApprovalExpiredError, ApprovalRequiredError
from domain.models import ActionProposal, Approval, AuditEvent
from repositories.base import GovernanceRepository
from services.approval_service import ApprovalService


DISALLOWED_ACTOR_PREFIXES = (
    "reliabilityagent",
    "coco",
    "agent",
    "systemagent",
    "autonomous",
    "bot",
    "orchestrator",
    "ml_engine",
    "pipeline",
)


class ApprovalGateway:
    """Gateway enforcing human governance over all operational action proposals."""

    def __init__(
        self,
        repository: GovernanceRepository,
        approval_service: Optional[ApprovalService] = None,
    ) -> None:
        self.repo = repository
        self.approval_service = approval_service or ApprovalService(repository=repository)

    def submit_proposal(self, proposal: ActionProposal) -> ActionProposal:
        """Submit an action proposal for human approval review."""
        if hasattr(self.repo, "get_action_proposal"):
            existing = self.repo.get_action_proposal(proposal.proposal_id)
            if existing:
                return existing

        now = datetime.now(timezone.utc)
        proposal_to_save = proposal.model_copy(
            update={
                "status": ActionProposalStatus.PENDING_APPROVAL.value,
                "updated_at": now,
            }
        )
        if hasattr(self.repo, "save_action_proposal"):
            saved = self.repo.save_action_proposal(proposal_to_save)
        else:
            saved = proposal_to_save

        # Create linked Approval entity
        approval = Approval(
            approval_id=f"APP-{proposal.proposal_id}",
            action_proposal_id=proposal.proposal_id,
            investigation_id=proposal.investigation_id,
            machine_id=proposal.machine_id,
            requested_action=proposal.action_type,
            status=ApprovalStatus.PENDING,
            requested_by="ReliabilityAgent",
            authorization_context={
                "priority": proposal.priority,
                "reason": proposal.reason,
                "parameters": proposal.parameters,
            },
        )
        self.approval_service.request_approval(approval)

        self._log_audit(
            actor="ReliabilityAgent",
            action_type="ACTION_PROPOSAL_SUBMITTED",
            resource_id=proposal.proposal_id,
            details={
                "machine_id": proposal.machine_id,
                "action_type": proposal.action_type,
                "approval_id": approval.approval_id,
            },
        )
        return saved

    def approve_proposal(
        self,
        proposal_id: str,
        approver_id: str,
        reason: str,
        authorization_context: Optional[Dict[str, Any]] = None,
    ) -> Approval:
        """Approve an action proposal by an authenticated human operator."""
        self._validate_actor(approver_id)

        # Retrieve proposal
        if not hasattr(self.repo, "get_action_proposal"):
            raise ValueError("Governance repository does not support action proposals.")

        proposal = self.repo.get_action_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"ActionProposal '{proposal_id}' not found.")

        approval_id = f"APP-{proposal_id}"
        approval = self.approval_service.get_approval(approval_id)
        if not approval:
            # Fallback lookup or create pending approval
            approval = Approval(
                approval_id=approval_id,
                action_proposal_id=proposal_id,
                investigation_id=proposal.investigation_id,
                machine_id=proposal.machine_id,
                requested_action=proposal.action_type,
                status=ApprovalStatus.PENDING,
                requested_by="ReliabilityAgent",
            )
            self.approval_service.request_approval(approval)

        # Delegate approval lifecycle check to approval service
        approved_record = self.approval_service.approve_action(
            approval_id=approval_id,
            approver_id=approver_id,
            reason=reason,
        )

        # Transition proposal status to APPROVED
        updated_proposal = proposal.model_copy(
            update={
                "status": ActionProposalStatus.APPROVED.value,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        if hasattr(self.repo, "update_action_proposal"):
            self.repo.update_action_proposal(updated_proposal)

        return approved_record

    def reject_proposal(
        self,
        proposal_id: str,
        approver_id: str,
        reason: str,
    ) -> Approval:
        """Reject an action proposal by an authenticated human operator."""
        self._validate_actor(approver_id)

        if not hasattr(self.repo, "get_action_proposal"):
            raise ValueError("Governance repository does not support action proposals.")

        proposal = self.repo.get_action_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"ActionProposal '{proposal_id}' not found.")

        approval_id = f"APP-{proposal_id}"
        rejected_record = self.approval_service.reject_action(
            approval_id=approval_id,
            approver_id=approver_id,
            reason=reason,
        )

        # Transition proposal status to REJECTED
        updated_proposal = proposal.model_copy(
            update={
                "status": ActionProposalStatus.REJECTED.value,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        if hasattr(self.repo, "update_action_proposal"):
            self.repo.update_action_proposal(updated_proposal)

        return rejected_record

    def _validate_actor(self, actor: str) -> None:
        """Prevent self-approval by autonomous agents or bots."""
        if not actor or not actor.strip():
            raise ValueError("Approver actor identity cannot be empty.")

        normalized = actor.strip().lower()
        if any(normalized.startswith(p) for p in DISALLOWED_ACTOR_PREFIXES):
            raise PermissionError(
                f"Actor '{actor}' is an autonomous agent or system process. "
                "Only authorized human operators may approve or reject operational proposals."
            )

    def _log_audit(self, actor: str, action_type: str, resource_id: str, details: Dict[str, Any]) -> None:
        if hasattr(self.repo, "log_audit"):
            event = AuditEvent(
                audit_id=f"AUD-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
                actor=actor,
                action_type=action_type,
                resource_id=resource_id,
                resource_type="APPROVAL_GATEWAY",
                details=details,
            )
            self.repo.log_audit(event)
