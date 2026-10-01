"""Governed M4 Read-Only Tool Registry and Action Firewall.

Enforces:
- Strict READ-only tool classification (ToolMode.READ)
- Immediate hard rejection of any mutating or action tool (M5 firewall)
- Explicit prohibition of arbitrary SQL execution tools
- Complete audit logging and execution duration tracking
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from domain.enums import ToolMode
from tools.read.base import BaseReadTool

from tools.read.prediction_tools import (
    GetPredictionTool,
    GetPredictionLineageTool,
    GetFeatureSnapshotTool,
)
from tools.read.sensor_tools import GetSensorContextTool
from tools.read.asset_tools import GetMachineContextTool, GetMachineHealthTool
from tools.read.maintenance_tools import (
    GetMaintenanceHistoryTool,
    GetHistoricalFailuresTool,
)
from tools.read.downtime_tools import GetDowntimeHistoryTool
from tools.read.supply_chain_tools import (
    GetInventoryRiskTool,
    GetProductionContextTool,
)
from tools.read.knowledge_tools import (
    SearchKnowledgeTool,
    GetKnowledgeDocumentTool,
)

logger = logging.getLogger(__name__)

FORBIDDEN_NAME_PATTERNS = ["execute_sql", "run_query", "raw_sql", "mutate", "create_work_order", "approve", "purchase"]


class ActionFirewallError(PermissionError):
    """Raised when an action or unrestricted query capability is introduced into the read-only M4 registry."""
    pass


class M4InvestigationToolRegistry:
    """Governed registry managing typed, read-only tools for autonomous investigation."""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseReadTool] = {}

    def register(self, tool: BaseReadTool) -> None:
        """Register a read-only tool behind strict M4 security firewalls."""
        # 1. Enforce ToolMode.READ
        mode = getattr(tool, "tool_mode", None) or getattr(tool, "mode", None)
        if mode != ToolMode.READ and str(mode).upper() != "READ":
            raise ActionFirewallError(
                f"M4 Firewall violation: Tool '{tool.name}' declares mode '{mode}'. "
                "Only ToolMode.READ tools are permitted in Milestone 4."
            )

        # 2. Enforce Arbitrary SQL and Action Pattern Prohibition
        tool_name_lower = tool.name.lower()
        for pattern in FORBIDDEN_NAME_PATTERNS:
            if pattern in tool_name_lower:
                raise ActionFirewallError(
                    f"M4 Security violation: Tool '{tool.name}' matches prohibited pattern '{pattern}'. "
                    "Unrestricted SQL and operational mutations are strictly forbidden."
                )

        # 3. Enforce Read-Only Scope
        scope = getattr(tool, "scope", "")
        if "action" in scope.lower() or "write" in scope.lower() or "admin" in scope.lower():
            raise ActionFirewallError(
                f"M4 Firewall violation: Tool '{tool.name}' declares mutating scope '{scope}'."
            )

        self._tools[tool.name] = tool
        logger.debug("Registered M4 read tool: %s (%s)", tool.name, tool.scope)

    def get_tool(self, name: str) -> BaseReadTool:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered in M4 tool registry.")
        return self._tools[name]

    def list_tools(self) -> List[BaseReadTool]:
        return list(self._tools.values())

    def list_tool_names(self) -> List[str]:
        return list(self._tools.keys())

    def execute_tool(self, name: str, execution_id: str = "ADHOC", **kwargs: Any) -> Any:
        """Execute a registered read-only tool with full audit logging."""
        tool = self.get_tool(name)
        return tool.execute(execution_id=execution_id, **kwargs)


def create_m4_tool_registry(repository: Any) -> M4InvestigationToolRegistry:
    """Build and validate the official Milestone 4 Read-Only Tool Catalog."""
    registry = M4InvestigationToolRegistry()

    # 1. Prediction Tools
    registry.register(GetPredictionTool(repository))
    registry.register(GetPredictionLineageTool(repository))
    registry.register(GetFeatureSnapshotTool(repository))

    # 2. Telemetry & Sensor Tools
    registry.register(GetSensorContextTool(repository))

    # 3. Asset & Machine Context Tools
    registry.register(GetMachineContextTool(repository))
    registry.register(GetMachineHealthTool(repository))

    # 4. Maintenance & Failure History Tools
    registry.register(GetMaintenanceHistoryTool(repository))
    registry.register(GetHistoricalFailuresTool(repository))

    # 5. Downtime Tools
    registry.register(GetDowntimeHistoryTool(repository))

    # 6. Supply Chain & Production Context Tools
    registry.register(GetInventoryRiskTool(repository))
    registry.register(GetProductionContextTool(repository))

    # 7. Knowledge Tools
    registry.register(SearchKnowledgeTool(repository))
    registry.register(GetKnowledgeDocumentTool(repository))

    return registry
