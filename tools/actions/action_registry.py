"""Governed M5 Action Tool Registry and Action Firewall.

Enforces:
- Strict ACTION tool classification (ToolMode.ACTION)
- Hard rejection of READ-only tools or non-action tools in the action registry
- Absolute firewall against arbitrary SQL, raw queries, or unbounded mutating patterns
- Complete audit logging and execution tracking
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from domain.enums import ToolMode
from domain.exceptions import DomainError
from tools.actions.base import BaseActionTool
from tools.actions.work_order_actions import CreateWorkOrderAction
from tools.actions.inventory_actions import ReserveSparePartAction
from tools.actions.assignment_actions import AssignTechnicianAction

logger = logging.getLogger(__name__)

FORBIDDEN_ACTION_PATTERNS = ["execute_sql", "run_query", "raw_sql", "eval", "drop_table", "truncate"]


class ActionRegistryError(DomainError):
    """Raised when an invalid tool is registered in M5ActionRegistry or security violation occurs."""
    pass


class M5ActionRegistry:
    """Governed registry managing typed, consequential action tools behind human approval boundaries."""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseActionTool] = {}

    def register(self, tool: BaseActionTool) -> None:
        """Register an action tool behind strict M5 security firewalls."""
        # 1. Enforce ToolMode.ACTION
        mode = getattr(tool, "tool_mode", None)
        if mode != ToolMode.ACTION and str(mode).upper() != "ACTION":
            raise ActionRegistryError(
                f"M5 Registry violation: Tool '{tool.name}' declares mode '{mode}'. "
                "Only ToolMode.ACTION tools are permitted in the Milestone 5 Action Registry."
            )

        # 2. Reject Arbitrary SQL / dangerous execution patterns
        tool_name_lower = tool.name.lower()
        for pattern in FORBIDDEN_ACTION_PATTERNS:
            if pattern in tool_name_lower:
                raise ActionRegistryError(
                    f"M5 Security violation: Action tool '{tool.name}' matches prohibited pattern '{pattern}'. "
                    "Arbitrary database mutations and raw execution are strictly forbidden."
                )

        # 3. Reject Read-only scopes
        scope = getattr(tool, "scope", "")
        if "read" in scope.lower() or "query" in scope.lower():
            raise ActionRegistryError(
                f"M5 Registry violation: Action tool '{tool.name}' declares read/query scope '{scope}'."
            )

        self._tools[tool.name] = tool
        logger.debug("Registered M5 action tool: %s (%s)", tool.name, tool.scope)

    def get_tool(self, name: str) -> BaseActionTool:
        if name not in self._tools:
            raise KeyError(f"Action tool '{name}' is not registered in M5 action registry.")
        return self._tools[name]

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def list_tools(self) -> List[BaseActionTool]:
        return list(self._tools.values())

    def list_tool_names(self) -> List[str]:
        return list(self._tools.keys())

    def execute_tool(
        self,
        name: str,
        caller_actor: str,
        execution_id: str = "ADHOC",
        **kwargs: Any,
    ) -> Any:
        """Execute a registered action tool with full approval and audit enforcement."""
        tool = self.get_tool(name)
        return tool.execute(caller_actor=caller_actor, execution_id=execution_id, **kwargs)


def create_m5_action_registry(
    approval_service: Any,
    work_order_service: Any,
    supply_chain_repo: Any,
    maintenance_repo: Any,
    governance_repo: Optional[Any] = None,
) -> M5ActionRegistry:
    """Factory creating and populating the standard M5 Action Registry."""
    registry = M5ActionRegistry()

    # 1. Create Work Order Action
    registry.register(
        CreateWorkOrderAction(
            approval_service=approval_service,
            work_order_service=work_order_service,
            governance_repo=governance_repo,
        )
    )

    # 2. Reserve Spare Part Action
    registry.register(
        ReserveSparePartAction(
            approval_service=approval_service,
            supply_chain_repo=supply_chain_repo,
            governance_repo=governance_repo,
        )
    )

    # 3. Assign Technician Action
    registry.register(
        AssignTechnicianAction(
            approval_service=approval_service,
            maintenance_repo=maintenance_repo,
            governance_repo=governance_repo,
        )
    )

    return registry
