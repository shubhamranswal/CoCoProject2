"""Test suite for Milestone 4 Action Firewall and SQL Execution Prohibition.

Verifies:
- Hard rejection of any action/mutating tool attempted to be registered
- Hard rejection of arbitrary SQL query execution tools
- Complete absence of operational mutators in the M4 tool catalog
"""

import pytest
from pydantic import BaseModel
from domain.enums import ToolMode
from repositories.memory.memory_repository import InMemoryRepository
from tools.registry import (
    M4InvestigationToolRegistry,
    ActionFirewallError,
    create_m4_tool_registry,
)
from tools.read.base import BaseReadTool


@pytest.fixture
def repo():
    return InMemoryRepository(seed=True)


@pytest.fixture
def registry(repo):
    return create_m4_tool_registry(repo)


def test_m4_registry_contains_only_read_tools(registry: M4InvestigationToolRegistry):
    """Hard check that registry contains ONLY read tools and zero action tools."""
    tool_names = registry.list_tool_names()
    forbidden_terms = ["create_work_order", "approve", "purchase", "stop_machine", "start_machine", "sql", "query"]

    for name in tool_names:
        for term in forbidden_terms:
            assert term not in name.lower(), f"Prohibited tool name found: {name}"

        tool = registry.get_tool(name)
        assert tool.tool_mode == ToolMode.READ
        assert tool.mode == "READ"
        assert "action" not in tool.scope.lower()
        assert "write" not in tool.scope.lower()


def test_firewall_blocks_action_mode_tool():
    """Attempting to register a tool with non-READ mode must raise ActionFirewallError."""
    registry = M4InvestigationToolRegistry()

    class FakeActionTool(BaseReadTool):
        name = "custom_fake_tool"
        description = "Fake action"
        scope = "action:write"
        tool_mode = ToolMode.ACTION  # type: ignore

        def _run(self, params):
            return None

    with pytest.raises(ActionFirewallError, match="M4 Firewall violation"):
        registry.register(FakeActionTool(None))


def test_firewall_blocks_arbitrary_sql_patterns():
    """Attempting to register a tool with SQL query patterns must raise ActionFirewallError."""
    registry = M4InvestigationToolRegistry()

    class ExecuteSqlTool(BaseReadTool):
        name = "execute_sql_query"
        description = "Runs arbitrary SQL"
        scope = "sql:read"
        tool_mode = ToolMode.READ

        def _run(self, params):
            return None

    with pytest.raises(ActionFirewallError, match="M4 Security violation"):
        registry.register(ExecuteSqlTool(None))

    class RunQueryTool(BaseReadTool):
        name = "run_query"
        description = "Runs database query"
        scope = "db:read"
        tool_mode = ToolMode.READ

        def _run(self, params):
            return None

    with pytest.raises(ActionFirewallError, match="M4 Security violation"):
        registry.register(RunQueryTool(None))


def test_firewall_blocks_mutating_scope():
    """Attempting to register a tool with mutating scope must raise ActionFirewallError."""
    registry = M4InvestigationToolRegistry()

    class MutatingScopeTool(BaseReadTool):
        name = "safe_name_tool"
        description = "Mutates backend data"
        scope = "core:write"
        tool_mode = ToolMode.READ

        def _run(self, params):
            return None

    with pytest.raises(ActionFirewallError, match="mutating scope"):
        registry.register(MutatingScopeTool(None))
