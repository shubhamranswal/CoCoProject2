"""Read tools package export and tool catalog."""

from __future__ import annotations

from typing import Any, Dict

from tools.read.base import BaseReadTool
from tools.read.asset_tools import GetMachineContextTool
from tools.read.telemetry_tools import (
    GetRecentTelemetryTool,
    GetTelemetryFeaturesTool,
    GetActiveAnomaliesTool,
    GetFailureRiskTool,
)
from tools.read.operational_tools import (
    GetAlertContextTool,
    GetFailureHistoryTool,
    GetMaintenanceHistoryTool,
    GetOpenWorkOrdersTool,
    GetOEEImpactTool,
)
from tools.read.knowledge_tools import (
    GetMachineDocumentationTool,
    GetRelatedKnowledgeTool,
)


class ReadToolCatalog:
    """Convenience container managing all typed read tools bound to a repository."""

    def __init__(self, repository: Any) -> None:
        self.machine_context = GetMachineContextTool(repository)
        self.recent_telemetry = GetRecentTelemetryTool(repository)
        self.telemetry_features = GetTelemetryFeaturesTool(repository)
        self.active_anomalies = GetActiveAnomaliesTool(repository)
        self.failure_risk = GetFailureRiskTool(repository)
        self.alert_context = GetAlertContextTool(repository)
        self.failure_history = GetFailureHistoryTool(repository)
        self.maintenance_history = GetMaintenanceHistoryTool(repository)
        self.open_work_orders = GetOpenWorkOrdersTool(repository)
        self.oee_impact = GetOEEImpactTool(repository)
        self.machine_documentation = GetMachineDocumentationTool(repository)
        self.related_knowledge = GetRelatedKnowledgeTool(repository)

    def all_tools(self) -> Dict[str, BaseReadTool]:
        return {
            self.machine_context.name: self.machine_context,
            self.recent_telemetry.name: self.recent_telemetry,
            self.telemetry_features.name: self.telemetry_features,
            self.active_anomalies.name: self.active_anomalies,
            self.failure_risk.name: self.failure_risk,
            self.alert_context.name: self.alert_context,
            self.failure_history.name: self.failure_history,
            self.maintenance_history.name: self.maintenance_history,
            self.open_work_orders.name: self.open_work_orders,
            self.oee_impact.name: self.oee_impact,
            self.machine_documentation.name: self.machine_documentation,
            self.related_knowledge.name: self.related_knowledge,
        }

    def get_tool(self, name: str) -> BaseReadTool:
        tools = self.all_tools()
        if name not in tools:
            raise KeyError(f"Tool '{name}' not found in ReadToolCatalog")
        return tools[name]

    @property
    def call_history(self) -> list:
        history = []
        for tool in self.all_tools().values():
            history.extend(tool.call_history)
        return history


__all__ = [
    "BaseReadTool",
    "ReadToolCatalog",
    "GetMachineContextTool",
    "GetRecentTelemetryTool",
    "GetTelemetryFeaturesTool",
    "GetActiveAnomaliesTool",
    "GetFailureRiskTool",
    "GetAlertContextTool",
    "GetFailureHistoryTool",
    "GetMaintenanceHistoryTool",
    "GetOpenWorkOrdersTool",
    "GetOEEImpactTool",
    "GetMachineDocumentationTool",
    "GetRelatedKnowledgeTool",
]
