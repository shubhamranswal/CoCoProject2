"""Agent execution and tool invocation tracking models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from domain.enums import AgentStatus, TriggerType


class ToolCall(BaseModel):
    tool_call_id: str
    execution_id: str
    tool_name: str
    arguments: Dict[str, Any]
    result: Optional[Any] = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = 0.0
    is_success: bool = True
    error_message: Optional[str] = None


class AgentExecution(BaseModel):
    execution_id: str
    agent_name: str
    workflow_name: str
    trigger_type: TriggerType
    trigger_id: Optional[str] = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    status: AgentStatus = AgentStatus.RUNNING
    input_context: Dict[str, Any] = Field(default_factory=dict)
    output_summary: Optional[str] = None
    tool_calls: List[ToolCall] = Field(default_factory=list)
