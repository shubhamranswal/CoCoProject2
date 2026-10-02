"""Governed Action Execution Service.

Follows Milestone 5 Zero-Trust Architecture:
- Zero-trust pipeline: Proposal -> Approval Verification -> Preconditions -> Idempotency -> Typed Execution -> Audit -> State Transition
- CoCo and autonomous agents cannot bypass approval or execute directly
- Precondition failure (such as SP-002 stockout) produces safe rejection without corrupting state
- Idempotent execution (duplicate idempotency keys return the prior execution result)
- Full governance audit trail
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from domain.enums import ActionProposalStatus, ApprovalStatus
from domain.exceptions import (
    ApprovalExpiredError,
    ApprovalRequiredError,
    UnsupportedOperationError,
)
from domain.models import ActionExecution, ActionProposal, AuditEvent
from repositories.base import GovernanceRepository
from services.action_precondition_service import ActionPreconditionService
from services.approval_service import ApprovalService
from tools.actions.action_registry import M5ActionRegistry


DISALLOWED_ACTOR_PREFIXES = (
    "reliabilityagent",
    "coco",
    "agent",
    "systemagent",
    "system",
    "autonomous",
    "bot",
    "orchestrator",
    "ml_engine",
    "pipeline",
)


class ActionExecutionService:
    """Orchestrates zero-trust, governed execution of approved operational action proposals."""

    def __init__(
        self,
        governance_repo: GovernanceRepository,
        action_registry: M5ActionRegistry,
        precondition_service: ActionPreconditionService,
        approval_service: Optional[ApprovalService] = None,
        verification_service: Optional[Any] = None,
    ) -> None:
        self.gov_repo = governance_repo
        self.action_registry = action_registry
        self.precondition_service = precondition_service
        self.approval_service = approval_service or ApprovalService(repository=governance_repo)
        self.verification_service = verification_service

    def execute_proposal(
        self,
        proposal_id: str,
        caller_actor: str,
        idempotency_key: Optional[str] = None,
        execution_id: Optional[str] = None,
    ) -> ActionExecution:
        """Execute an approved action proposal through the zero-trust pipeline."""
        self._validate_actor(caller_actor)

        now = datetime.now(timezone.utc)
        exec_id = execution_id or f"EXE-{proposal_id}-{int(now.timestamp())}"

        # 1. Retrieve ActionProposal
        if not hasattr(self.gov_repo, "get_action_proposal"):
            raise ValueError("Repository does not support action proposals.")

        proposal = self.gov_repo.get_action_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"ActionProposal '{proposal_id}' not found.")

        # Idempotency Check: if prior successful execution exists for key, return immediately
        target_idem = idempotency_key or proposal.idempotency_key
        if target_idem and hasattr(self.gov_repo, "list_action_executions"):
            existing_executions = self.gov_repo.list_action_executions(action_proposal_id=proposal_id)
            for ex in existing_executions:
                if ex.idempotency_key == target_idem and ex.status == "SUCCESS":
                    return ex

        # 2. Verify Proposal Status
        if proposal.status != ActionProposalStatus.APPROVED.value:
            raise ApprovalRequiredError(
                f"Cannot execute proposal '{proposal_id}': status is '{proposal.status}', "
                f"must be '{ActionProposalStatus.APPROVED.value}'."
            )

        # 3. Verify Linked Approval
        approval_id = f"APP-{proposal_id}"
        approval = self.approval_service.get_approval(approval_id)
        if not approval:
            raise ApprovalRequiredError(f"Linked Approval '{approval_id}' not found.")

        if approval.status != ApprovalStatus.APPROVED:
            raise ApprovalRequiredError(
                f"Action proposal '{proposal_id}' has approval record in status "
                f"'{approval.status.value}', must be 'APPROVED'."
            )

        if approval.expires_at and now > approval.expires_at:
            raise ApprovalExpiredError(
                f"Approval '{approval_id}' expired at {approval.expires_at}."
            )

        # 4. Precondition Evaluation
        preconditions = self.precondition_service.validate_preconditions(
            action_type=proposal.action_type,
            machine_id=proposal.machine_id,
            component_id=proposal.parameters.get("component_id"),
            part_id=proposal.parameters.get("part_id"),
            qty=proposal.parameters.get("qty", 1),
            technician_id=proposal.parameters.get("technician_id") or proposal.parameters.get("assigned_to"),
            idempotency_key=target_idem,
            parameters=proposal.parameters,
        )

        if not preconditions.can_proceed:
            error_msg = "; ".join(preconditions.errors)
            failed_execution = ActionExecution(
                execution_id=exec_id,
                action_proposal_id=proposal_id,
                approval_id=approval_id,
                action_type=proposal.action_type,
                machine_id=proposal.machine_id,
                executed_by=caller_actor,
                status="FAILED",
                idempotency_key=target_idem,
                result_data={"precondition_details": preconditions.details, "errors": preconditions.errors},
                error_message=f"Preconditions violated: {error_msg}",
                started_at=now,
                completed_at=datetime.now(timezone.utc),
            )
            if hasattr(self.gov_repo, "save_action_execution"):
                self.gov_repo.save_action_execution(failed_execution)

            # Update proposal status to EXECUTION_BLOCKED
            if hasattr(self.gov_repo, "update_action_proposal"):
                self.gov_repo.update_action_proposal(
                    proposal.model_copy(
                        update={
                            "status": ActionProposalStatus.EXECUTION_BLOCKED.value,
                            "updated_at": datetime.now(timezone.utc),
                        }
                    )
                )

            self._log_audit(
                actor=caller_actor,
                action_type="ACTION_EXECUTION_BLOCKED_PRECONDITIONS",
                resource_id=exec_id,
                details={"errors": preconditions.errors, "proposal_id": proposal_id},
            )
            return failed_execution

        # 6. Mark Proposal as EXECUTING
        if hasattr(self.gov_repo, "update_action_proposal"):
            self.gov_repo.update_action_proposal(
                proposal.model_copy(
                    update={
                        "status": ActionProposalStatus.EXECUTING.value,
                        "updated_at": datetime.now(timezone.utc),
                    }
                )
            )

        # 7. Execute Typed Action Tool
        tool_name = self._resolve_tool_name(proposal.action_type)
        if not self.action_registry.has_tool(tool_name):
            raise UnsupportedOperationError(
                f"Action type '{proposal.action_type}' is not supported by any registered action tool.",
                entity_id=proposal_id,
            )

        if tool_name == "create_work_order":
            desc = (
                proposal.parameters.get("description")
                or proposal.parameters.get("action_description")
                or proposal.reason
            )
            title = (
                proposal.parameters.get("title")
                or f"Inspect {proposal.machine_id} {proposal.component_id or ''}".strip()
            )
            checklist = (
                proposal.parameters.get("checklist")
                or proposal.parameters.get("suggested_checklist")
                or []
            )
            tool_args = {
                "approval_id": approval_id,
                "machine_id": proposal.machine_id,
                "component_id": proposal.component_id or proposal.parameters.get("component_id") or "UNKNOWN",
                "title": title,
                "description": desc,
                "priority": proposal.priority,
                "checklist": checklist,
                "investigation_id": proposal.investigation_id,
                "recommendation_id": proposal.recommendation_id,
                "idempotency_key": target_idem,
                **proposal.parameters,
            }
            tool_args["title"] = title
            tool_args["description"] = desc
            tool_args["checklist"] = checklist
            tool_args["idempotency_key"] = target_idem
            if "assigned_to" not in proposal.parameters and "technician_id" not in proposal.parameters:
                tool_args["assigned_to"] = None
        else:
            tool_args = {
                "approval_id": approval_id,
                "machine_id": proposal.machine_id,
                "idempotency_key": target_idem,
                **proposal.parameters,
            }

        try:
            tool_result = self.action_registry.execute_tool(
                name=tool_name,
                caller_actor=caller_actor,
                execution_id=exec_id,
                **tool_args,
            )

            # Check if tool result returned internal shortage/failure (e.g. inventory shortage)
            tool_success = getattr(tool_result, "success", True)
            tool_dict = tool_result.model_dump(mode="json") if hasattr(tool_result, "model_dump") else {"result": str(tool_result)}

            if not tool_success:
                status = "FAILED"
                error_text = getattr(tool_result, "message", "Action tool returned failure.")
                next_proposal_status = ActionProposalStatus.FAILED.value
            else:
                status = "SUCCESS"
                error_text = None
                next_proposal_status = ActionProposalStatus.EXECUTED.value

            completed_at = datetime.now(timezone.utc)
            execution = ActionExecution(
                execution_id=exec_id,
                action_proposal_id=proposal_id,
                approval_id=approval_id,
                action_type=proposal.action_type,
                machine_id=proposal.machine_id,
                executed_by=caller_actor,
                status=status,
                idempotency_key=target_idem,
                result_data=tool_dict,
                error_message=error_text,
                started_at=now,
                completed_at=completed_at,
            )

            if hasattr(self.gov_repo, "save_action_execution"):
                self.gov_repo.save_action_execution(execution)

            if hasattr(self.gov_repo, "update_action_proposal"):
                self.gov_repo.update_action_proposal(
                    proposal.model_copy(
                        update={
                            "status": next_proposal_status,
                            "updated_at": completed_at,
                        }
                    )
                )

            self._log_audit(
                actor=caller_actor,
                action_type=f"ACTION_EXECUTION_{status}",
                resource_id=exec_id,
                details={
                    "proposal_id": proposal_id,
                    "action_type": proposal.action_type,
                    "tool_name": tool_name,
                    "status": status,
                },
            )
            return execution

        except Exception as exc:
            completed_at = datetime.now(timezone.utc)
            failed_execution = ActionExecution(
                execution_id=exec_id,
                action_proposal_id=proposal_id,
                approval_id=approval_id,
                action_type=proposal.action_type,
                machine_id=proposal.machine_id,
                executed_by=caller_actor,
                status="FAILED",
                idempotency_key=target_idem,
                result_data={"error": str(exc)},
                error_message=str(exc),
                started_at=now,
                completed_at=completed_at,
            )
            if hasattr(self.gov_repo, "save_action_execution"):
                self.gov_repo.save_action_execution(failed_execution)

            if hasattr(self.gov_repo, "update_action_proposal"):
                self.gov_repo.update_action_proposal(
                    proposal.model_copy(
                        update={
                            "status": ActionProposalStatus.FAILED.value,
                            "updated_at": completed_at,
                        }
                    )
                )

            self._log_audit(
                actor=caller_actor,
                action_type="ACTION_EXECUTION_EXCEPTION",
                resource_id=exec_id,
                details={"proposal_id": proposal_id, "error": str(exc)},
            )
            raise

    def _resolve_tool_name(self, action_type: str) -> str:
        """Map canonical action type to registered action tool name."""
        norm = action_type.strip().lower()
        if "work_order" in norm or "inspect" in norm:
            return "create_work_order"
        if "part" in norm or "inventory" in norm or "reserve" in norm:
            return "reserve_spare_part"
        if "assign" in norm or "technician" in norm:
            return "assign_technician"
        return action_type

    def _validate_actor(self, actor: str) -> None:
        """Prevent execution by autonomous agents, bots, system processes, or empty actor identity."""
        if not actor or not actor.strip():
            raise ValueError("Actor identity cannot be empty.")

        normalized = actor.strip().lower()
        if any(normalized.startswith(p) for p in DISALLOWED_ACTOR_PREFIXES):
            raise PermissionError(
                f"Actor '{actor}' is an autonomous agent or system process. "
                "Only authorized human operators may execute operational action proposals."
            )

    def verify_proposal_execution(
        self,
        proposal_id: str,
        execution_id: str,
        work_order_id: str,
        investigation_id: str,
        machine_id: str,
        pre_features: Optional[Any] = None,
        post_features: Optional[Any] = None,
        pre_risk: Optional[Any] = None,
        post_risk: Optional[Any] = None,
        pre_oee: Optional[Any] = None,
        post_oee: Optional[Any] = None,
        active_anomalies: Optional[List[Any]] = None,
        policy: Optional[Any] = None,
        verifier: str = "SYSTEM",
        prediction_id: Optional[str] = None,
        downtime_avoided_hours: float = 0.0,
        is_simulated_telemetry: bool = False,
        telemetry_provenance: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Bridge connecting executed action to physical verification and outcome recording."""
        if not self.verification_service:
            raise ValueError("VerificationService is not configured on ActionExecutionService.")

        return self.verification_service.verify_recovery(
            work_order_id=work_order_id,
            investigation_id=investigation_id,
            machine_id=machine_id,
            pre_features=pre_features,
            post_features=post_features,
            pre_risk=pre_risk,
            post_risk=post_risk,
            pre_oee=pre_oee,
            post_oee=post_oee,
            active_anomalies=active_anomalies,
            policy=policy,
            verifier=verifier,
            action_proposal_id=proposal_id,
            execution_id=execution_id,
            prediction_id=prediction_id,
            downtime_avoided_hours=downtime_avoided_hours,
            is_simulated_telemetry=is_simulated_telemetry,
            telemetry_provenance=telemetry_provenance,
        )

    def _log_audit(self, actor: str, action_type: str, resource_id: str, details: Dict[str, Any]) -> None:
        if hasattr(self.gov_repo, "log_audit"):
            event = AuditEvent(
                audit_id=f"AUD-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
                actor=actor,
                action_type=action_type,
                resource_id=resource_id,
                resource_type="ACTION_EXECUTION",
                details=details,
            )
            self.gov_repo.log_audit(event)
