"""Base class and common infrastructure for typed read tools.

Follows AGENT.md & architecture/architecture.md:
- Strictly typed input and output schemas (Pydantic)
- Narrow scope (no unrestricted SQL or raw database mutations)
- Bound checking (no unbounded scans or runaway queries)
- Auditable tool call tracking via ToolCall model
- Safe failure handling
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel, ValidationError

from domain.enums import ToolMode
from domain.models import ToolCall


class BaseReadTool(ABC):
    """Abstract base class for all auditable read tools."""

    name: str = ""
    description: str = ""
    scope: str = "read"
    tool_mode: ToolMode = ToolMode.READ
    mode: str = "READ"
    authorization_boundary: str = "READ_ONLY"
    input_schema: Type[BaseModel] = BaseModel
    output_schema: Type[BaseModel] = BaseModel

    def __init__(self, repository: Any) -> None:
        self.repo = repository
        self._call_history: list[ToolCall] = []

    @property
    def call_history(self) -> list[ToolCall]:
        return list(self._call_history)

    def execute(self, execution_id: str = "ADHOC", **kwargs: Any) -> Any:
        """Validate inputs, execute tool logic, record audit event, and return typed output."""
        start_t = time.perf_counter()
        started_at = datetime.now(timezone.utc)
        call_id = f"TC-{self.name}-{int(started_at.timestamp() * 1000)}"

        # 1. Validate Input
        try:
            validated_input = self.input_schema(**kwargs)
        except ValidationError as err:
            duration_ms = round((time.perf_counter() - start_t) * 1000.0, 2)
            tc = ToolCall(
                tool_call_id=call_id,
                execution_id=execution_id,
                tool_name=self.name,
                arguments=kwargs,
                result=None,
                started_at=started_at,
                duration_ms=duration_ms,
                is_success=False,
                error_message=f"Input validation error: {err}",
            )
            self._call_history.append(tc)
            raise ValueError(f"Tool {self.name} input validation failed: {err}") from err

        # 2. Execute Implementation
        try:
            raw_result = self._run(validated_input)
            duration_ms = round((time.perf_counter() - start_t) * 1000.0, 2)
            tc = ToolCall(
                tool_call_id=call_id,
                execution_id=execution_id,
                tool_name=self.name,
                arguments=validated_input.model_dump(mode="json"),
                result={"status": "SUCCESS"},
                started_at=started_at,
                duration_ms=duration_ms,
                is_success=True,
                error_message=None,
            )
            self._call_history.append(tc)
            return raw_result
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_t) * 1000.0, 2)
            tc = ToolCall(
                tool_call_id=call_id,
                execution_id=execution_id,
                tool_name=self.name,
                arguments=kwargs,
                result=None,
                started_at=started_at,
                duration_ms=duration_ms,
                is_success=False,
                error_message=str(exc),
            )
            self._call_history.append(tc)
            raise

    @abstractmethod
    def _run(self, params: Any) -> Any:
        """Specific tool logic implemented by subclasses."""
        ...
