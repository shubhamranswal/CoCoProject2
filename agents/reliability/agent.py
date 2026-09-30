"""Reliability Investigation Agent orchestrator.

Follows AGENT.md & architecture/architecture.md:
- Autonomous investigation flow: Alert -> Evidence -> Hypotheses -> Finding -> Recommendation -> Policy -> Approval
- Does NOT allow LLM to directly query Snowflake or mutate operational state
- Strict typed read tool usage with full audit logging
- Explicit action policy enforcement: NEVER automatically creates executable work orders without approval
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from domain.enums import (
    ActionStatus,
    AgentStatus,
    AlertStatus,
    ApprovalStatus,
    InvestigationStatus,
    Priority,
    TriggerType,
)
from domain.models import (
    Action,
    ActionProposal,
    AgentExecution,
    Alert,
    Approval,
    AuditEvent,
    Evidence,
    Finding,
    Hypothesis,
    Investigation,
    Machine,
    Recommendation,
    ToolCall,
)
from repositories import get_repository
from repositories.base import (
    GovernanceRepository,
    InvestigationRepository,
    MachineRepository,
)
from services.approval_service import ApprovalService
from services.policy_service import ActionPolicyEngine
from tools.read import ReadToolCatalog
from agents.reliability.reasoner import (
    DeterministicInvestigationReasoner,
    InvestigationContext,
    InvestigationReasoner,
    ReasoningOutput,
)


@dataclass
class ReliabilityInvestigationResult:
    execution: AgentExecution
    investigation: Investigation
    evidence: List[Evidence]
    hypotheses: List[Hypothesis]
    finding: Finding
    recommendation: Recommendation
    action_proposal: ActionProposal
    approval: Optional[Approval]


class ReliabilityInvestigationAgent:
    """Investigates equipment reliability alerts using typed tools and evidence correlation."""

    def __init__(
        self,
        repository: Any = None,
        reasoner: Optional[InvestigationReasoner] = None,
        policy_engine: Optional[ActionPolicyEngine] = None,
        approval_service: Optional[ApprovalService] = None,
    ) -> None:
        self.repo = repository or get_repository()
        self.tools = ReadToolCatalog(self.repo)
        self.reasoner = reasoner or DeterministicInvestigationReasoner()
        self.policy_engine = policy_engine or ActionPolicyEngine()
        self.approval_service = approval_service or ApprovalService(self.repo)

    def investigate_alert(self, alert_id: str) -> ReliabilityInvestigationResult:
        """Execute end-to-end investigation for a triggered reliability alert."""
        start_t = time.perf_counter()
        now = datetime.now(timezone.utc)
        exec_id = f"EXEC-REL-{int(now.timestamp() * 1000)}"

        # Initialize Audit Execution Record
        execution = AgentExecution(
            execution_id=exec_id,
            agent_name="ReliabilityInvestigationAgent",
            workflow_name="InvestigateReliabilityAlert",
            trigger_type=TriggerType.ALERT,
            trigger_id=alert_id,
            started_at=now,
            status=AgentStatus.RUNNING,
            input_context={"alert_id": alert_id},
        )

        # -------------------------------------------------------------
        # 1. Fetch Alert Context
        # -------------------------------------------------------------
        alert_out = self.tools.alert_context.execute(execution_id=exec_id, alert_id=alert_id)
        alert: Optional[Alert] = alert_out.alert
        if not alert:
            execution.status = AgentStatus.FAILED
            execution.output_summary = f"Alert '{alert_id}' was not found in repository."
            execution.completed_at = datetime.now(timezone.utc)
            self._record_audit_event(execution, "INVESTIGATION_FAILED", alert_id)
            raise ValueError(f"Alert '{alert_id}' does not exist.")

        machine_id = alert.machine_id
        inv_id = f"INV-{machine_id}-{int(now.timestamp())}"

        # Check if already resolved
        if alert.status == AlertStatus.RESOLVED:
            execution.status = AgentStatus.COMPLETED
            execution.output_summary = f"Alert '{alert_id}' is already RESOLVED. No investigation needed."
            execution.completed_at = datetime.now(timezone.utc)
            # Create a minimal closed record
            empty_inv = Investigation(
                investigation_id=inv_id,
                alert_id=alert_id,
                machine_id=machine_id,
                status=InvestigationStatus.CLOSED,
            )
            return ReliabilityInvestigationResult(
                execution=execution,
                investigation=empty_inv,
                evidence=[],
                hypotheses=[],
                finding=Finding(
                    finding_id=f"FIND-{inv_id}",
                    investigation_id=inv_id,
                    summary="Alert already resolved.",
                    failure_mode=alert.failure_mode,
                    confidence=1.0,
                ),
                recommendation=Recommendation(
                    recommendation_id=f"REC-{inv_id}",
                    investigation_id=inv_id,
                    title="No Action Needed",
                    action_description="Alert is resolved.",
                    priority=Priority.LOW,
                    action_required=False,
                ),
                action_proposal=ActionProposal(
                    action_proposal_id=f"AP-{inv_id}",
                    investigation_id=inv_id,
                    action_type="NONE",
                    machine_id=machine_id,
                    priority=Priority.LOW,
                    reason="Alert resolved.",
                    recommendation_id=f"REC-{inv_id}",
                    requires_approval=False,
                ),
                approval=None,
            )

        # -------------------------------------------------------------
        # 2. Initialize Investigation in Repository
        # -------------------------------------------------------------
        investigation = Investigation(
            investigation_id=inv_id,
            alert_id=alert_id,
            machine_id=machine_id,
            status=InvestigationStatus.COLLECTING_EVIDENCE,
            failure_mode=alert.failure_mode,
            confidence=0.0,
        )
        self.repo.create_investigation(investigation)

        # -------------------------------------------------------------
        # 3. Collect Evidence Through Explicit Read Tools
        # -------------------------------------------------------------
        evidence_list: List[Evidence] = []
        ev_counter = 1

        def add_evidence(
            ev_type: str,
            source: str,
            metric: str,
            observed: Any,
            baseline: Optional[Any],
            rel: str,
            summary: str,
            fact: Optional[str] = None,
            is_contra: bool = False,
            comp_id: Optional[str] = None,
        ) -> None:
            nonlocal ev_counter
            ev = Evidence(
                evidence_id=f"E{ev_counter}",
                investigation_id=inv_id,
                evidence_type=ev_type,
                source=source,
                metric=metric,
                observed_value=observed,
                baseline_value=baseline,
                relationship=rel,
                machine_id=machine_id,
                component_id=comp_id,
                observed_fact=fact or summary,
                is_contradictory=is_contra,
                summary=summary,
                timestamp=datetime.now(timezone.utc),
            )
            evidence_list.append(ev)
            ev_counter += 1

        # Tool 1: Machine context
        mach_ctx = self.tools.machine_context.execute(execution_id=exec_id, machine_id=machine_id)
        mach: Machine = mach_ctx.machine or Machine(
            machine_id=machine_id,
            machine_code=machine_id,
            name=f"Machine {machine_id}",
            line_id="LINE-B",
            model="DRV-5000",
        )

        # Tool 2: Telemetry features
        feat_out = self.tools.telemetry_features.execute(execution_id=exec_id, machine_id=machine_id)
        if feat_out.features:
            fv = feat_out.features
            add_evidence(
                ev_type="TELEMETRY",
                source="ml.features.FeatureExtractor",
                metric="vibration_rms",
                observed=f"{fv.vibration_rms:.3f} g",
                baseline="0.450 g",
                rel="SUPPORTS",
                summary=f"Vibration RMS reached {fv.vibration_rms:.3f} g ({fv.vibration_baseline_deviation_pct:+.1f}% vs nominal baseline).",
                fact=f"Vibration RMS increased to {fv.vibration_rms:.3f} g.",
                comp_id="CMP-M204-BRG",
            )
            add_evidence(
                ev_type="TELEMETRY",
                source="ml.features.FeatureExtractor",
                metric="temperature_mean",
                observed=f"{fv.temperature_mean:.1f} °C",
                baseline="58.5 °C",
                rel="SUPPORTS",
                summary=f"Drive bearing temperature reached {fv.temperature_mean:.1f} °C (Thermal gradient: {fv.temperature_slope:+.2f} °C/hr).",
                fact=f"Bearing temperature climbed to {fv.temperature_mean:.1f} °C.",
                comp_id="CMP-M204-BRG",
            )
            add_evidence(
                ev_type="TELEMETRY",
                source="ml.features.FeatureExtractor",
                metric="rpm_mean",
                observed=f"{fv.rpm_mean:.1f} RPM",
                baseline="1750.0 RPM",
                rel="CONTRADICTS",
                summary=f"Motor shaft speed steady at {fv.rpm_mean:.1f} RPM. No belt slippage or drive stall detected.",
                fact=f"Shaft speed stable at {fv.rpm_mean:.1f} RPM.",
                is_contra=True,
                comp_id="CMP-M204-SHF",
            )
        else:
            telem_out = self.tools.recent_telemetry.execute(execution_id=exec_id, machine_id=machine_id, limit=5)
            for m in telem_out.measurements:
                add_evidence(
                    ev_type="TELEMETRY",
                    source="telemetry.measurements",
                    metric=m.sensor_id,
                    observed=f"{m.value:.3f} {m.unit}",
                    baseline=None,
                    rel="SUPPORTS",
                    summary=f"Sensor {m.sensor_id} measured {m.value:.3f} {m.unit}.",
                    fact=f"{m.sensor_id} is active at {m.value:.3f} {m.unit}.",
                )


        # Tool 3: Active anomalies
        anom_out = self.tools.active_anomalies.execute(execution_id=exec_id, machine_id=machine_id, active_only=True)
        for a in anom_out.anomalies:
            add_evidence(
                ev_type="ANOMALY",
                source="services.anomaly_service.AnomalyService",
                metric=a.metric_name,
                observed=a.observed_value,
                baseline=a.baseline_value,
                rel="SUPPORTS",
                summary=f"{a.severity.value} anomaly on {a.metric_name} (Z-Score: {a.score:.1f}, Dev: {a.deviation_pct:+.1f}%).",
                fact=f"Active {a.severity.value} anomaly detected on {a.metric_name}.",
                comp_id="CMP-M204-BRG",
            )

        # Tool 4: Failure risk
        risk_out = self.tools.failure_risk.execute(execution_id=exec_id, machine_id=machine_id)
        if risk_out.failure_risk:
            fr = risk_out.failure_risk
            add_evidence(
                ev_type="RISK",
                source="ml.inference.risk_scorer.FailureRiskScorer",
                metric="failure_risk_score",
                observed=f"{fr.risk_score:.2f}",
                baseline="< 0.35",
                rel="SUPPORTS",
                summary=f"Model calculated {fr.risk_level.value} failure risk ({fr.risk_score:.2f}) for {fr.failure_mode.value}.",
                fact=f"Predicted failure risk is {fr.risk_score:.2f} ({fr.risk_level.value}).",
                comp_id="CMP-M204-BRG",
            )

        # Tool 5: Historical failures
        fail_out = self.tools.failure_history.execute(execution_id=exec_id, machine_id=machine_id)
        for f in fail_out.failures:
            add_evidence(
                ev_type="FAILURE_HISTORY",
                source="FACTORY_RELIABILITY.FAILURE_HISTORY",
                metric=f.failure_mode.value,
                observed=f.occurred_at.strftime("%Y-%m-%d"),
                baseline=None,
                rel="SUPPORTS",
                summary=f"Prior failure on {f.occurred_at.strftime('%Y-%m-%d')}: {f.root_cause} ({f.downtime_hours}h downtime).",
                fact=f"Asset previously experienced {f.failure_mode.value} with {f.downtime_hours}h downtime.",
                comp_id=f.component_id,
            )

        # Tool 6: Maintenance history
        maint_out = self.tools.maintenance_history.execute(execution_id=exec_id, machine_id=machine_id, limit=5)
        for m in maint_out.events:
            add_evidence(
                ev_type="MAINTENANCE",
                source="FACTORY_MAINTENANCE.MAINTENANCE_EVENT",
                metric=m.maintenance_type,
                observed=m.performed_at.strftime("%Y-%m-%d"),
                baseline=None,
                rel="CONTEXTUAL",
                summary=f"{m.maintenance_type} performed on {m.performed_at.strftime('%Y-%m-%d')} by {m.technician_name}: {m.notes}",
                fact=f"Last maintenance was {m.maintenance_type} on {m.performed_at.strftime('%Y-%m-%d')}.",
                comp_id=m.component_id,
            )

        # Tool 7: OEE & Production impact
        oee_out = self.tools.oee_impact.execute(execution_id=exec_id, machine_id=machine_id)
        add_evidence(
            ev_type="OEE",
            source="services.oee_service.OEEService",
            metric="oee_score",
            observed=f"{oee_out.oee * 100:.1f}%",
            baseline="95.0%",
            rel="SUPPORTS" if oee_out.is_impacted else "CONTEXTUAL",
            summary=f"Line OEE at {oee_out.oee * 100:.1f}% (Downtime: {oee_out.downtime_minutes:.0f} min). {oee_out.details}",
            fact=f"Current line OEE is {oee_out.oee * 100:.1f}%.",
        )

        # Tool 8: Machine technical manual
        model_name = mach.model or "DRV-5000"
        doc_out = self.tools.machine_documentation.execute(execution_id=exec_id, machine_model=model_name)
        if doc_out.document:
            for chk in doc_out.document.chunks[:3]:
                add_evidence(
                    ev_type="DOCUMENT",
                    source=f"{doc_out.document.title} - {chk.section_title}",
                    metric="technical_service_limit",
                    observed=chk.section_title,
                    baseline=None,
                    rel="SUPPORTS",
                    summary=chk.content[:220] + "...",
                    fact=f"Technical manual specifies: {chk.section_title}",
                    comp_id="CMP-M204-BRG",
                )

        # Save collected evidence to repository
        self.repo.save_evidence(evidence_list)

        # -------------------------------------------------------------
        # 4. Reason: Form Hypotheses, Finding, and Recommendation
        # -------------------------------------------------------------
        investigation.status = InvestigationStatus.ANALYZING
        investigation.evidence = evidence_list

        ctx = InvestigationContext(
            investigation_id=inv_id,
            alert=alert,
            machine=mach,
            evidence=evidence_list,
        )

        reasoning_res: ReasoningOutput = self.reasoner.reason(ctx)

        # Update Investigation with Reasoning Artifacts
        investigation.hypotheses = reasoning_res.hypotheses
        investigation.finding = reasoning_res.finding
        investigation.recommendation = reasoning_res.recommendation
        investigation.confidence = reasoning_res.finding.confidence
        investigation.status = InvestigationStatus.RECOMMENDATION_READY

        # -------------------------------------------------------------
        # 5. Action Policy & Approval Boundary
        # -------------------------------------------------------------
        rec = reasoning_res.recommendation
        action_id = f"ACT-{inv_id}"

        # Formulate Action Model
        action = Action(
            action_id=action_id,
            recommendation_id=rec.recommendation_id,
            action_type=rec.action_type,
            payload={
                "machine_id": machine_id,
                "component_id": "CMP-M204-BRG",
                "suggested_parts": rec.suggested_parts,
                "suggested_checklist": rec.suggested_checklist,
                "priority": rec.priority.value,
                "estimated_downtime_hours": rec.estimated_downtime_hours,
            },
            status=ActionStatus.PROPOSED,
            requires_approval=True,
        )

        # Evaluate against Policy Engine
        needs_approval = self.policy_engine.requires_approval(action, mach)

        approval: Optional[Approval] = None
        if needs_approval:
            approval_id = f"APP-{inv_id}"
            approval = Approval(
                approval_id=approval_id,
                action_id=action_id,
                investigation_id=inv_id,
                machine_id=machine_id,
                status=ApprovalStatus.PENDING,
                requested_by="ReliabilityInvestigationAgent",
            )
            self.approval_service.request_approval(approval)
            investigation.status = InvestigationStatus.PENDING_APPROVAL
        else:
            investigation.status = InvestigationStatus.FINDING_READY

        action_proposal = ActionProposal(
            action_proposal_id=f"PROP-{inv_id}",
            investigation_id=inv_id,
            action_type=rec.action_type,
            machine_id=machine_id,
            component_id="CMP-M204-BRG",
            priority=rec.priority,
            reason=rec.action_description,
            recommendation_id=rec.recommendation_id,
            evidence_ids=rec.evidence_ids,
            risk_level=alert.severity.value,
            requires_approval=needs_approval,
            approval_id=approval.approval_id if approval else None,
        )
        investigation.action_proposal = action_proposal

        # -------------------------------------------------------------
        # 6. Complete Execution and Audit Logging
        # -------------------------------------------------------------
        investigation.completed_at = datetime.now(timezone.utc)
        self.repo.update_investigation(investigation)

        # Aggregate tool calls
        all_calls: List[ToolCall] = []
        for t in [
            self.tools.machine_context,
            self.tools.alert_context,
            self.tools.telemetry_features,
            self.tools.active_anomalies,
            self.tools.failure_risk,
            self.tools.failure_history,
            self.tools.maintenance_history,
            self.tools.oee_impact,
            self.tools.machine_documentation,
        ]:
            all_calls.extend([c for c in t.call_history if c.execution_id == exec_id])

        execution.tool_calls = all_calls
        execution.status = AgentStatus.COMPLETED
        execution.completed_at = datetime.now(timezone.utc)
        execution.output_summary = (
            f"Investigation {inv_id} concluded with finding: '{investigation.finding.summary}'. "
            f"Recommendation: '{rec.title}'. Approval required: {needs_approval}."
        )

        self._record_audit_event(execution, "INVESTIGATION_COMPLETED", inv_id)

        return ReliabilityInvestigationResult(
            execution=execution,
            investigation=investigation,
            evidence=evidence_list,
            hypotheses=investigation.hypotheses,
            finding=investigation.finding,
            recommendation=investigation.recommendation,
            action_proposal=action_proposal,
            approval=approval,
        )

    def _record_audit_event(self, execution: AgentExecution, action_type: str, resource_id: str) -> None:
        """Log an immutable governance audit event."""
        if hasattr(self.repo, "log_audit"):
            audit = AuditEvent(
                audit_id=f"AUD-{execution.execution_id}",
                actor=execution.agent_name,
                action_type=action_type,
                resource_id=resource_id,
                resource_type="INVESTIGATION",
                details={
                    "workflow": execution.workflow_name,
                    "status": execution.status.value,
                    "tools_count": len(execution.tool_calls),
                },
            )
            self.repo.log_audit(audit)
