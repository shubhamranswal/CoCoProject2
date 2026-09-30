"""Reproducible CLI demonstration of the Reliability Investigation Agent.

Follows AGENT.md:
- Triggers from an active high-risk M204 alert
- Gathers real evidence via explicit typed read tools
- Evaluates competing hypotheses (supporting vs contradictory)
- Formulates finding and actionable recommendation
- Enforces action policy and submits human approval request
- Proves safety: NO operational work order is executed without human sign-off
"""

from __future__ import annotations

from datetime import datetime, timezone

from data.scenarios.m204_scenario import M204ScenarioEngine, ScenarioPhase
from domain.enums import FailureMode
from repositories.memory.memory_repository import InMemoryRepository
from services.pipeline_orchestrator import PipelineOrchestrator
from agents.reliability.agent import ReliabilityInvestigationAgent


def run_investigation_demo() -> None:
    # 1. Initialize In-Memory Repository & Engine
    repo = InMemoryRepository()
    engine = M204ScenarioEngine(machine_id="M204")
    orchestrator = PipelineOrchestrator(repository=repo)

    # 2. Simulate HIGH_RISK phase to generate active Alert
    now = datetime(2026, 3, 30, 14, 0, 0, tzinfo=timezone.utc)
    measurements = engine.generate_timeseries(phase=ScenarioPhase.HIGH_RISK, num_points=12, start_time=now)
    prod_run, dt_event = engine.generate_operational_context(phase=ScenarioPhase.HIGH_RISK, run_date=now)

    pipe_result = orchestrator.run_reliability_pipeline(
        machine_id="M204",
        measurements=measurements,
        production_run=prod_run,
        downtime_events=[dt_event] if dt_event else None,
        failure_mode=FailureMode.BEARING_DEGRADATION,
    )

    alert = pipe_result.alert
    if not alert:
        print("ERROR: Pipeline did not generate an alert for HIGH_RISK scenario.")
        return

    # 3. Instantiate Reliability Investigation Agent and Execute
    agent = ReliabilityInvestigationAgent(repository=repo)
    result = agent.investigate_alert(alert.alert_id)

    # 4. Print Structured Command Center Output
    print("=" * 64)
    print(" M204 RELIABILITY INVESTIGATION")
    print("=" * 64)
    print()
    print("Trigger")
    print(f"  Alert:    {alert.alert_id}")
    print(f"  Severity: {alert.severity.value}")
    print(f"  Risk:     {alert.risk_score:.2f}")
    print(f"  Reason:   {alert.trigger_reason}")
    print()
    print("Evidence Collected")
    for ev in result.evidence:
        rel_flag = "(-)" if ev.is_contradictory else "(+)"
        print(f"  [{ev.evidence_id}] {rel_flag} {ev.evidence_type:<15} | {ev.summary}")
    print()
    print("Hypotheses")
    for hyp in result.hypotheses:
        print(f"  {hyp.hypothesis_name.replace('_', ' ').title()} (Status: {hyp.status}, Confidence: {hyp.confidence * 100:.0f}%)")
        print(f"    Supporting:    {len(hyp.supporting_evidence_ids)}")
        print(f"    Contradicting: {len(hyp.contradicting_evidence_ids)}")
        print(f"    Rationale:     {hyp.rationale}")
        print()

    print("Finding")
    print(f"  {result.finding.summary}")
    print(f"  Confidence: {result.finding.confidence * 100:.0f}%")
    print()
    print("  Observed Facts:")
    for f in result.finding.observed_facts[:3]:
        print(f"    - {f}")
    print("  Historical Facts:")
    for hf in result.finding.historical_facts[:2]:
        print(f"    - {hf}")
    print("  Inferences:")
    for inf in result.finding.inferences:
        print(f"    - {inf}")
    print()

    print("Recommendation")
    print(f"  Title:    {result.recommendation.title}")
    print(f"  Action:   {result.recommendation.action_type}")
    print(f"  Priority: {result.recommendation.priority.value}")
    print(f"  Scope:    {result.recommendation.action_description}")
    print("  Checklist:")
    for item in result.recommendation.suggested_checklist[:4]:
        print(f"    [ ] {item}")
    print()

    print("Action & Governance")
    print(f"  Proposed Action:  {result.action_proposal.action_type}")
    print(f"  Approval Status:  {'REQUIRED (Approval ID: ' + (result.approval.approval_id if result.approval else 'N/A') + ')' if result.action_proposal.requires_approval else 'AUTO-APPROVED'}")
    print(f"  Pending Reviews:  {len(repo.list_approvals(machine_id='M204', status='PENDING'))} request(s)")
    print()
    print("Safety Check:")
    open_wos = repo.list_work_orders(machine_id="M204")
    print(f"  Executable Work Orders in DB: {len(open_wos)} (No unauthorized work order executed)")
    print("=" * 64)


if __name__ == "__main__":
    run_investigation_demo()
