"""Approval service managing human-in-the-loop workflows.

Follows AGENT.md & architecture/architecture.md:
- Explicit human actor required: approve_action(approval_id, approver_id, reason)
- Autonomous agents strictly prohibited from self-approving actions
- Strict state validation (rejects double-approval, expired, or non-existent approvals)
- Idempotent: repeated identical approval by same approver returns existing record
- Full governance audit logging
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from domain.enums import ApprovalStatus
from domain.models import Approval, AuditEvent
from repositories.base import GovernanceRepository


class ApprovalService:
    """Manages human approval requests and lifecycle transitions."""

    def __init__(self, repository: GovernanceRepository) -> None:
        self.repo = repository

    def request_approval(self, approval: Approval) -> Approval:
        """Create a new pending approval request."""
        return self.repo.create_approval(approval)

    def get_approval(self, approval_id: str) -> Optional[Approval]:
        """Retrieve approval record by ID."""
        return self.repo.get_approval(approval_id)

    def approve_action(self, approval_id: str, approver_id: str, reason: str) -> Approval:
        """Explicitly approve an operational action by an authenticated human actor."""
        self._validate_actor(approver_id)

        app = self.repo.get_approval(approval_id)
        if not app:
            raise ValueError(f"Approval '{approval_id}' not found.")

        # Check expiration
        now = datetime.now(timezone.utc)
        if app.expires_at and now > app.expires_at:
            self.repo.update_approval(
                approval_id,
                status=ApprovalStatus.EXPIRED,
                reviewer=approver_id,
                reason="Approval request expired before decision.",
            )
            raise ValueError(f"Approval '{approval_id}' has expired.")

        # Check existing resolved states
        if app.status == ApprovalStatus.APPROVED:
            # Idempotency check: same approver, same decision
            if app.decision_by == approver_id or app.reviewed_by == approver_id:
                return app
            raise ValueError(f"Approval '{approval_id}' is already approved by {app.decision_by or app.reviewed_by}.")

        if app.status == ApprovalStatus.REJECTED:
            raise ValueError(f"Approval '{approval_id}' was already rejected.")

        if app.status in (ApprovalStatus.EXPIRED, ApprovalStatus.CANCELLED):
            raise ValueError(f"Cannot approve an approval in status {app.status.value}.")

        # Execute approval transition
        updated = self.repo.update_approval(
            approval_id=approval_id,
            status=ApprovalStatus.APPROVED,
            reviewer=approver_id,
            reason=reason,
        )

        # Update decision fields
        updated_app = updated.model_copy(
            update={
                "decision_by": approver_id,
                "decision_at": now,
                "decision_reason": reason,
                "reviewed_by": approver_id,
                "reviewed_at": now,
            }
        )
        if hasattr(self.repo, "_approvals"):
            self.repo._approvals[approval_id] = updated_app

        # Log audit event
        self._log_audit(
            actor=approver_id,
            action_type="APPROVAL_GRANTED",
            resource_id=approval_id,
            details={
                "machine_id": app.machine_id,
                "investigation_id": app.investigation_id,
                "reason": reason,
            },
        )
        return updated_app

    def reject_action(self, approval_id: str, approver_id: str, reason: str) -> Approval:
        """Explicitly reject an operational action by an authenticated human actor."""
        self._validate_actor(approver_id)

        app = self.repo.get_approval(approval_id)
        if not app:
            raise ValueError(f"Approval '{approval_id}' not found.")

        if app.status == ApprovalStatus.APPROVED:
            raise ValueError(f"Cannot reject approval '{approval_id}'; action has already been approved.")

        if app.status == ApprovalStatus.REJECTED:
            if app.decision_by == approver_id or app.reviewed_by == approver_id:
                return app
            raise ValueError(f"Approval '{approval_id}' was already rejected.")

        now = datetime.now(timezone.utc)
        updated = self.repo.update_approval(
            approval_id=approval_id,
            status=ApprovalStatus.REJECTED,
            reviewer=approver_id,
            reason=reason,
        )
        updated_app = updated.model_copy(
            update={
                "decision_by": approver_id,
                "decision_at": now,
                "decision_reason": reason,
                "reviewed_by": approver_id,
                "reviewed_at": now,
            }
        )
        if hasattr(self.repo, "_approvals"):
            self.repo._approvals[approval_id] = updated_app

        self._log_audit(
            actor=approver_id,
            action_type="APPROVAL_REJECTED",
            resource_id=approval_id,
            details={
                "machine_id": app.machine_id,
                "investigation_id": app.investigation_id,
                "reason": reason,
            },
        )
        return updated_app

    def review_approval(
        self, approval_id: str, status: ApprovalStatus, reviewer: str, reason: str
    ) -> Approval:
        """Legacy review method delegating to explicit approval/rejection."""
        if status == ApprovalStatus.APPROVED:
            return self.approve_action(approval_id, reviewer, reason)
        elif status == ApprovalStatus.REJECTED:
            return self.reject_action(approval_id, reviewer, reason)
        else:
            return self.repo.update_approval(approval_id, status=status, reviewer=reviewer, reason=reason)

    def list_pending_approvals(self, machine_id: Optional[str] = None) -> List[Approval]:
        """List all pending approval requests awaiting human review."""
        return self.repo.list_approvals(machine_id=machine_id, status=ApprovalStatus.PENDING)

    def _validate_actor(self, actor: str) -> None:
        """Prevent self-approval by autonomous agents or anonymous callers."""
        if not actor or not actor.strip():
            raise ValueError("Approver actor identity cannot be empty.")

        disallowed_prefixes = (
            "reliabilityagent",
            "agent",
            "systemagent",
            "autonomous",
            "bot",
            "orchestrator",
        )
        normalized = actor.strip().lower()
        if any(normalized.startswith(p) for p in disallowed_prefixes):
            raise PermissionError(
                f"Actor '{actor}' is an autonomous agent. Only authorized human operators may approve actions."
            )

    def _log_audit(self, actor: str, action_type: str, resource_id: str, details: dict) -> None:
        if hasattr(self.repo, "log_audit"):
            event = AuditEvent(
                audit_id=f"AUD-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
                actor=actor,
                action_type=action_type,
                resource_id=resource_id,
                resource_type="APPROVAL",
                details=details,
            )
            self.repo.log_audit(event)
