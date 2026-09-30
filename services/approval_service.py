"""Approval service managing human-in-the-loop workflows."""

from __future__ import annotations

from typing import List, Optional

from domain.enums import ApprovalStatus
from domain.models import Approval
from repositories.base import GovernanceRepository


class ApprovalService:
    def __init__(self, repository: GovernanceRepository) -> None:
        self.repo = repository

    def request_approval(self, approval: Approval) -> Approval:
        return self.repo.create_approval(approval)

    def review_approval(
        self, approval_id: str, status: ApprovalStatus, reviewer: str, reason: str
    ) -> Approval:
        return self.repo.update_approval(approval_id, status=status, reviewer=reviewer, reason=reason)

    def list_pending_approvals(self, machine_id: Optional[str] = None) -> List[Approval]:
        return self.repo.list_approvals(machine_id=machine_id, status=ApprovalStatus.PENDING)
