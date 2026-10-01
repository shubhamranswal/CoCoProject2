"""Base class and common infrastructure for governed action tools.

Follows AGENT.md & architecture/architecture.md:
- Governed execution: action tools require explicit, valid human approval
- Zero-trust client parameters: client-supplied 'approved=True' or bypasses are strictly rejected
- Verification of approval status, target machine, and expiration against the repository
- Auditable tool call tracking via ToolCall model and AuditEvent
- Idempotent action execution
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, ValidationError

from domain.enums import ApprovalStatus, ToolMode
from domain.exceptions import ApprovalExpiredError, ApprovalRequiredError, InvalidMachineError
from domain.models import AuditEvent, ToolCall
from repositories.base import GovernanceRepository
from services.approval_service import ApprovalService


class BaseActionTool(ABC):
    """Abstract base class for all governed operational action tools."""

    name: str = ""
    description: str = ""
    scope: str = "action"
    tool_mode: ToolMode = ToolMode.ACTION
    requires_approval: bool = True
    input_schema: Type[BaseModel] = BaseModel
    output_schema: Type[BaseModel] = BaseModel

    def __init__(
        self,
        approval_service: ApprovalService,
        governance_repo: Optional[GovernanceRepository] = None,
    ) -> None:
        self.approval_service = approval_service
        self.gov_repo = governance_repo
        self._call_history: List[ToolCall] = []

    @property
    def call_history(self) -> List[ToolCall]:
        return list(self._call_history)

    def execute(self, caller_actor: str, execution_id: str = "ADHOC", **kwargs: Any) -> Any:
        """Validate approval, validate inputs, execute action, and record audit trail."""
        start_t = time.perf_counter()
        started_at = datetime.now(timezone.utc)
        call_id = f"ACT-{self.name}-{int(started_at.timestamp() * 1000)}"

        # 1. Zero-Trust Check: reject client parameter spoofing
        if "approved" in kwargs or "bypass_approval" in kwargs or "force_approved" in kwargs:
            self._log_audit(
                actor=caller_actor,
                action_type=f"{self.name.upper()}_REJECTED_SPOOF",
                resource_id="SECURITY_VIOLATION",
                details={"error": "Client attempted to pass client-side approval bypass flag."},
            )
            raise PermissionError(
                "Client-supplied approval parameters are forbidden. "
                "Approval status is verified strictly from the server governance repository."
            )

        # 2. Governed Approval Verification
        if self.requires_approval:
            approval_id = kwargs.get("approval_id")
            if not approval_id:
                raise ApprovalRequiredError(f"Action '{self.name}' requires a valid 'approval_id'.")

            approval = self.approval_service.get_approval(approval_id)
            if not approval:
                raise ApprovalRequiredError(f"Approval record '{approval_id}' not found in repository.", entity_id=approval_id)

            if approval.status != ApprovalStatus.APPROVED:
                raise ApprovalRequiredError(
                    f"Action '{self.name}' rejected: Approval '{approval_id}' has status "
                    f"'{approval.status.value}', but must be 'APPROVED'.",
                    entity_id=approval_id,
                )

            # Check expiration
            now = datetime.now(timezone.utc)
            if approval.expires_at and now > approval.expires_at:
                raise ApprovalExpiredError(
                    f"Action '{self.name}' rejected: Approval '{approval_id}' expired at {approval.expires_at}.",
                    entity_id=approval_id,
                )

            # Check machine match if supplied
            target_machine = kwargs.get("machine_id")
            if target_machine and approval.machine_id != target_machine:
                raise InvalidMachineError(
                    f"Action '{self.name}' rejected: Target machine '{target_machine}' does not match "
                    f"approved machine '{approval.machine_id}'.",
                    entity_id=target_machine,
                )

        # 3. Input Validation
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
            raise ValueError(f"Action {self.name} input validation failed: {err}") from err

        # 4. Action Execution
        try:
            result = self._run(validated_input, caller_actor=caller_actor)
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
            self._log_audit(
                actor=caller_actor,
                action_type=f"{self.name.upper()}_SUCCESS",
                resource_id=getattr(result, "work_order_id", call_id),
                details={"execution_id": execution_id, "duration_ms": duration_ms},
            )
            return result
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
            self._log_audit(
                actor=caller_actor,
                action_type=f"{self.name.upper()}_FAILED",
                resource_id=call_id,
                details={"execution_id": execution_id, "error": str(exc)},
            )
            raise

    def _log_audit(self, actor: str, action_type: str, resource_id: str, details: Dict[str, Any]) -> None:
        if self.gov_repo and hasattr(self.gov_repo, "log_audit"):
            event = AuditEvent(
                audit_id=f"AUD-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
                actor=actor,
                action_type=action_type,
                resource_id=resource_id,
                resource_type="ACTION_TOOL",
                details=details,
            )
            self.gov_repo.log_audit(event)

    @abstractmethod
    def _run(self, params: Any, caller_actor: str) -> Any:
        """Subclass executes governed business logic."""
        ...
