"""Verification service validating post-maintenance recovery."""

from __future__ import annotations

from typing import Optional

from domain.models import Verification
from repositories.base import GovernanceRepository


class VerificationService:
    def __init__(self, repository: GovernanceRepository) -> None:
        self.repo = repository

    def record_verification(self, verification: Verification) -> None:
        self.repo.save_verification(verification)

    def get_verification(self, work_order_id: str) -> Optional[Verification]:
        return self.repo.get_verification(work_order_id)
