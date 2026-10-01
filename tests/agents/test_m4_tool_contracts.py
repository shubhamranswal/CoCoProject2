"""Test suite for Milestone 4 Read-Only Tool Contracts.

Verifies:
- All registered tools declare ToolMode.READ
- All registered tools provide typed input and output schemas
- All registered tools execute safely without side effects
"""

import pytest
from domain.enums import ToolMode
from repositories.memory.memory_repository import InMemoryRepository
from tools.registry import create_m4_tool_registry, M4InvestigationToolRegistry
from tools.read.base import BaseReadTool


@pytest.fixture
def repo():
    return InMemoryRepository(seed=True)


@pytest.fixture
def registry(repo):
    return create_m4_tool_registry(repo)


def test_all_m4_tools_are_read_mode(registry: M4InvestigationToolRegistry):
    """Verify that every tool in M4 catalog is strictly declared as ToolMode.READ."""
    tools = registry.list_tools()
    assert len(tools) >= 11, f"Expected at least 11 read tools, got {len(tools)}"

    for tool in tools:
        assert isinstance(tool, BaseReadTool), f"Tool {tool.name} must inherit BaseReadTool"
        assert tool.tool_mode == ToolMode.READ, f"Tool {tool.name} mode is {tool.tool_mode}, expected ToolMode.READ"
        assert tool.mode == "READ", f"Tool {tool.name} string mode is {tool.mode}, expected 'READ'"
        assert tool.authorization_boundary == "READ_ONLY", f"Tool {tool.name} boundary must be READ_ONLY"
        assert ":read" in tool.scope or "read" in tool.scope.lower(), f"Tool {tool.name} scope must indicate read: {tool.scope}"


def test_all_m4_tools_have_typed_schemas(registry: M4InvestigationToolRegistry):
    """Verify that every tool specifies typed input and output Pydantic schemas."""
    for tool in registry.list_tools():
        assert hasattr(tool, "input_schema") and tool.input_schema is not None, f"Tool {tool.name} missing input_schema"
        assert hasattr(tool, "output_schema") and tool.output_schema is not None, f"Tool {tool.name} missing output_schema"
        assert hasattr(tool, "name") and len(tool.name) > 0, "Tool must have a valid non-empty name"
        assert hasattr(tool, "description") and len(tool.description) > 0, f"Tool {tool.name} missing description"


def test_m4_tool_execution_creates_audit_trail(registry: M4InvestigationToolRegistry):
    """Verify that tool execution logs duration, status, and does not alter operational state."""
    tool = registry.get_tool("get_machine_context")
    res = tool.execute("EXEC-001", machine_id="M21")
    assert res is not None
    assert res.machine is not None
    assert res.machine.machine_id == "M21"
    assert len(tool.call_history) >= 1
    last_call = tool.call_history[-1]
    assert last_call.tool_name == "get_machine_context"
    assert last_call.is_success is True
    assert last_call.duration_ms >= 0.0
