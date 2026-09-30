"""Unit tests for typed read tools.

Follows AGENT.md:
- Input schema validation & parameter bounds
- Audit logging of tool executions into ToolCall
- Safe handling of missing entities
- Bounded scans
"""

import pytest
from pydantic import ValidationError

from repositories.memory.memory_repository import InMemoryRepository
from tools.read import (
    GetMachineContextTool,
    GetRecentTelemetryTool,
    GetTelemetryFeaturesTool,
    GetActiveAnomaliesTool,
    GetFailureRiskTool,
    GetAlertContextTool,
    GetFailureHistoryTool,
    GetMaintenanceHistoryTool,
    GetOpenWorkOrdersTool,
    GetOEEImpactTool,
    GetMachineDocumentationTool,
    GetRelatedKnowledgeTool,
    ReadToolCatalog,
)


@pytest.fixture
def repo():
    return InMemoryRepository()


def test_get_machine_context_valid(repo):
    tool = GetMachineContextTool(repo)
    res = tool.execute(execution_id="TEST-01", machine_id="M204")
    assert res.machine is not None
    assert res.machine.machine_id == "M204"
    assert len(res.components) > 0
    assert len(res.sensors) > 0
    assert len(tool.call_history) == 1
    assert tool.call_history[0].is_success is True


def test_get_machine_context_missing_machine(repo):
    tool = GetMachineContextTool(repo)
    res = tool.execute(execution_id="TEST-02", machine_id="NON_EXISTENT")
    assert res.machine is None
    assert len(res.components) == 0


def test_get_recent_telemetry_bounds_validation(repo):
    tool = GetRecentTelemetryTool(repo)

    # Valid bounded input
    res = tool.execute(execution_id="TEST-03", machine_id="M204", hours=24, limit=50)
    assert res.machine_id == "M204"

    # Input exceeding upper bound (hours > 168) should raise ValueError / ValidationError
    with pytest.raises(ValueError):
        tool.execute(execution_id="TEST-04", machine_id="M204", hours=1000)

    # Input below lower bound (limit < 1) should raise ValueError
    with pytest.raises(ValueError):
        tool.execute(execution_id="TEST-05", machine_id="M204", limit=0)


def test_get_alert_context_nonexistent(repo):
    tool = GetAlertContextTool(repo)
    res = tool.execute(execution_id="TEST-06", alert_id="ALT-DOES-NOT-EXIST")
    assert res.alert is None


def test_get_failure_and_maintenance_history(repo):
    fail_tool = GetFailureHistoryTool(repo)
    maint_tool = GetMaintenanceHistoryTool(repo)

    f_res = fail_tool.execute(execution_id="TEST-07", machine_id="M204")
    assert f_res.count >= 1
    assert "BEARING" in f_res.failures[0].failure_mode.value

    m_res = maint_tool.execute(execution_id="TEST-08", machine_id="M204", limit=10)
    assert m_res.count >= 1


def test_get_machine_documentation_and_knowledge(repo):
    doc_tool = GetMachineDocumentationTool(repo)
    know_tool = GetRelatedKnowledgeTool(repo)

    d_res = doc_tool.execute(execution_id="TEST-09", machine_model="DRV-5000")
    assert d_res.document is not None
    assert len(d_res.document.chunks) >= 3

    k_res = know_tool.execute(
        execution_id="TEST-10",
        machine_id="M204",
        query="bearing raceway vibration limits",
    )
    assert k_res.results_count >= 1
    assert "bearing" in k_res.results[0].content.lower()


def test_read_tool_catalog_lookup(repo):
    catalog = ReadToolCatalog(repo)
    t = catalog.get_tool("get_machine_context")
    assert t.name == "get_machine_context"

    with pytest.raises(KeyError):
        catalog.get_tool("unrestricted_sql_query")
