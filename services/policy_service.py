"""Policy service evaluating whether operational actions require human approval.

Follows AGENT.md:
- Consequential actions require policy evaluation
- Never hardcode approval logic into an LLM prompt alone
"""

from __future__ import annotations

from config import get_config
from domain.models import Action, Machine


class ActionPolicyEngine:
    def __init__(self) -> None:
        self.config = get_config()

    def requires_approval(self, action: Action, machine: Machine) -> bool:
        """Determines if the proposed action requires human sign-off."""
        if not self.config.features.require_human_approval_for_critical_assets:
            return False

        # Critical assets always require human approval for work order creation
        if machine.criticality in ("CRITICAL", "HIGH") and action.action_type in ("CREATE_WORK_ORDER", "SCHEDULE_SHUTDOWN"):
            return True

        return action.requires_approval
