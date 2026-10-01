"""Unit tests for tool registry isolation and firewall guarantees.

Validates:
- M4 registry strictly accepts only ToolMode.READ tools
- M4 firewall immediately rejects any action tool (ActionFirewallError)
- M5 registry strictly accepts only ToolMode.ACTION tools
- M5 firewall immediately rejects any read tool (ActionRegistryError)
- Neither registry permits arbitrary SQL or unsafe execution patterns
"""

import pytest

from domain.enums import ToolMode
from repositories.memory.memory_repository import InMemoryRepository
from tools.registry import M4InvestigationToolRegistry, ActionFirewallError, create_m4_tool_registry
from tools.actions.action_registry import M5ActionRegistry, ActionRegistryError, create_m5_action_registry
from tools.actions.base import BaseActionTool
from tools.read.base import BaseReadTool
from services.approval_service import ApprovalService
from services.work_order_service import WorkOrderService


class DummyActionTool(BaseActionTool):
    name = "dummy_action"
    tool_mode = ToolMode.ACTION
    scope = "action"

    def _run(self, params, caller_actor):
        return {"status": "ok"}


class DummyReadTool(BaseReadTool):
    name = "dummy_read"
    tool_mode = ToolMode.READ
    scope = "investigation"

    def _run(self, **kwargs):
        return {"data": "read_data"}


class ArbitrarySqlActionTool(BaseActionTool):
    name = "execute_sql_action"
    tool_mode = ToolMode.ACTION
    scope = "action"

    def _run(self, params, caller_actor):
        return {}


class ArbitrarySqlQueryTool(BaseReadTool):
    name = "run_query_tool"
    tool_mode = ToolMode.READ
    scope = "investigation"

    def _run(self, **kwargs):
        return {}


def test_m4_registry_rejects_action_tools():
    """M4InvestigationToolRegistry raises ActionFirewallError when registering an action tool."""
    m4_registry = M4InvestigationToolRegistry()
    app_svc = ApprovalService(repository=InMemoryRepository())
    action_tool = DummyActionTool(approval_service=app_svc)

    with pytest.raises(ActionFirewallError) as exc_info:
        m4_registry.register(action_tool)
    assert "M4 Firewall violation" in str(exc_info.value)


def test_m4_registry_rejects_prohibited_query_patterns():
    """M4 registry rejects tools with forbidden patterns like run_query."""
    m4_registry = M4InvestigationToolRegistry()
    unsafe_tool = ArbitrarySqlQueryTool(repository=InMemoryRepository())

    with pytest.raises(ActionFirewallError) as exc_info:
        m4_registry.register(unsafe_tool)
    assert "M4 Security violation" in str(exc_info.value)


def test_m5_registry_rejects_read_tools():
    """M5ActionRegistry raises ActionRegistryError when registering a read tool."""
    m5_registry = M5ActionRegistry()
    read_tool = DummyReadTool(repository=InMemoryRepository())

    with pytest.raises(ActionRegistryError) as exc_info:
        m5_registry.register(read_tool)
    assert "M5 Registry violation" in str(exc_info.value)


def test_m5_registry_rejects_prohibited_patterns():
    """M5 registry rejects tools matching arbitrary SQL patterns."""
    m5_registry = M5ActionRegistry()
    app_svc = ApprovalService(repository=InMemoryRepository())
    unsafe_action_tool = ArbitrarySqlActionTool(approval_service=app_svc)

    with pytest.raises(ActionRegistryError) as exc_info:
        m5_registry.register(unsafe_action_tool)
    assert "M5 Security violation" in str(exc_info.value)


def test_standard_registries_factory_isolation():
    """Factory-created standard registries are mutually isolated and properly configured."""
    repo = InMemoryRepository()
    app_svc = ApprovalService(repository=repo)
    wo_svc = WorkOrderService(repository=repo, governance_repo=repo)

    m4_registry = create_m4_tool_registry(repo)
    m5_registry = create_m5_action_registry(
        approval_service=app_svc,
        work_order_service=wo_svc,
        supply_chain_repo=repo,
        maintenance_repo=repo,
        governance_repo=repo,
    )

    # Check M4 tools are all READ
    for tool in m4_registry.list_tools():
        assert tool.tool_mode == ToolMode.READ
        assert "action" not in tool.name.lower()

    # Check M5 tools are all ACTION
    for tool in m5_registry.list_tools():
        assert tool.tool_mode == ToolMode.ACTION
        assert "read" not in tool.scope.lower()
