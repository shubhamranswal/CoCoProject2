# Agent Workflows

**Product:** Factory Reliability Command Center
**Document:** `agent-workflows.md`
**Version:** 1.0
**Status:** Foundational Agent Workflow Specification
**Primary Platform:** Snowflake
**Agent Development & Execution Surface:** CoCo
**Application:** Streamlit
**Architecture:** Multi-agent, tool-driven, governed, human-in-the-loop

---

# 1. Purpose

This document defines the operational workflows of the Factory Reliability Command Center's agentic intelligence layer.

It specifies:

* when agents are triggered
* which agent owns each workflow
* how agents obtain context
* which tools agents can use
* how agents reason over structured and unstructured data
* how agents collaborate
* how agents produce structured outputs
* how recommendations become actions
* when human approval is required
* how failures are handled
* how outcomes are verified
* how agent activity is audited
* how the system learns from completed workflows

The goal is to create an agentic system that behaves like an operational reliability team rather than a chatbot.

---

# 2. Core Principle

The agentic layer follows:

```text
OBSERVE
   ↓
UNDERSTAND
   ↓
INVESTIGATE
   ↓
DECIDE
   ↓
ACT
   ↓
VERIFY
   ↓
LEARN
```

The system should never collapse these stages into a single opaque LLM call.

For example:

```text
Sensor anomaly
      ↓
Reliability detection
      ↓
Investigation
      ↓
Evidence collection
      ↓
Failure hypothesis
      ↓
Recommendation
      ↓
Policy evaluation
      ↓
Approval
      ↓
Work order
      ↓
Maintenance
      ↓
Verification
```

Each stage produces structured state that can be audited.

---

# 3. Agent Architecture

The platform uses a specialized multi-agent architecture.

```text
                         ┌────────────────────┐
                         │ ORCHESTRATOR AGENT │
                         └─────────┬──────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    ▼                    ▼
      ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
      │ RELIABILITY  │     │     OEE      │     │   QUALITY    │
      │    AGENT     │     │    AGENT     │     │    AGENT     │
      └──────┬───────┘     └──────┬───────┘     └──────┬───────┘
             │                    │                    │
             └────────────────────┼────────────────────┘
                                  │
                                  ▼
                       ┌────────────────────┐
                       │   MAINTENANCE      │
                       │      AGENT         │
                       └─────────┬──────────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │ ACTION TOOLS  │
                         └───────────────┘
```

The initial implementation should use five logical agents:

1. Orchestrator Agent
2. Reliability Agent
3. OEE Agent
4. Quality Agent
5. Maintenance Agent

Additional specialist agents can be introduced later without changing the architecture.

---

# 4. Why Multiple Agents?

A single giant agent creates several problems:

```text
Too many tools
Too much context
Harder evaluation
Harder permissions
Harder debugging
Harder auditing
Harder reliability
```

Specialization allows:

```text
Reliability Agent
→ equipment health

OEE Agent
→ production effectiveness

Quality Agent
→ product/process quality

Maintenance Agent
→ operational maintenance

Orchestrator
→ coordination
```

Each agent has a narrower responsibility and toolset.

---

# 5. Agent Design Principles

Every agent must follow these principles.

## 5.1 Grounded

Agents reason from governed data.

```text
Snowflake
+
Semantic Layer
+
Knowledge
+
Tool Results
```

---

## 5.2 Tool-Based

Agents should obtain information through explicit tools.

They should not assume data.

---

## 5.3 Structured

Agents produce structured outputs.

Free-form text is an explanation layer, not the canonical workflow state.

---

## 5.4 Auditable

Every agent execution must record:

```text
agent
execution_id
trigger
inputs
tools
outputs
confidence
actions
errors
timestamp
```

---

## 5.5 Permissioned

Agents do not have unrestricted write access.

Read and write capabilities are explicitly separated.

---

## 5.6 Idempotent

Retries should not create duplicate operational actions.

---

## 5.7 Fail Safe

When evidence is insufficient, the agent should say:

```text
INSUFFICIENT_EVIDENCE
```

rather than inventing an explanation.

---

# 6. Agent Lifecycle

Every agent execution follows:

```text
TRIGGER
   ↓
CONTEXT RESOLUTION
   ↓
PLAN
   ↓
TOOL EXECUTION
   ↓
EVIDENCE COLLECTION
   ↓
REASONING
   ↓
STRUCTURED OUTPUT
   ↓
POLICY CHECK
   ↓
ACTION / ESCALATION
   ↓
AUDIT
```

Not every workflow reaches the action stage.

---

# 7. Agent Execution State

An execution can have the following states:

```text
CREATED
QUEUED
RUNNING
WAITING_FOR_TOOL
WAITING_FOR_APPROVAL
COMPLETED
FAILED
CANCELLED
BLOCKED
```

---

# 8. Agent Execution Record

Each execution should conceptually contain:

```text
agent_execution_id
agent_name
workflow_name
trigger_type
trigger_id
started_at
completed_at
status
input_context
tool_calls
finding
confidence
recommendation
action
error
```

---

# 9. Trigger Types

Agents may be triggered by:

### Event Trigger

```text
New anomaly
New alert
New quality event
```

### Schedule Trigger

```text
Daily reliability scan
Hourly asset health scan
Shift-based OEE analysis
```

### User Trigger

```text
"Why is M204 at risk?"
```

### Workflow Trigger

```text
Reliability Agent
→ Maintenance Agent
```

### External Trigger

```text
CMMS update
ERP event
Slack command
API request
```

---

# 10. Workflow Categories

The system supports:

```text
1. Reliability Detection
2. Reliability Investigation
3. Failure Prediction
4. Root Cause Investigation
5. OEE Investigation
6. Quality Investigation
7. Maintenance Planning
8. Work Order Creation
9. Maintenance Verification
10. Alert Triage
11. Natural Language Investigation
12. Scheduled Health Monitoring
13. Cross-Agent Investigation
14. Exception Handling
15. Learning / Feedback
```

---

# 11. Workflow 1: Reliability Detection

This workflow detects abnormal machine behavior.

```text
Telemetry
   ↓
Feature Pipeline
   ↓
Baseline
   ↓
Anomaly Detection
   ↓
Risk Score
   ↓
Alert
```

The Reliability Agent does not need to perform every mathematical calculation.

Deterministic and ML processing should happen before the agent is invoked.

---

# 12. Reliability Detection Inputs

```text
machine_id
sensor_id
measurement
timestamp
operating_regime
baseline
feature_values
anomaly_score
failure_risk
```

---

# 13. Reliability Detection Output

```text
alert_id
machine_id
severity
anomaly_type
risk_score
detected_at
trigger_reason
```

Example:

```text
Alert:

Machine:
M204

Signal:
Vibration RMS

Observed:
0.82 g

Baseline:
0.55 g

Deviation:
+49%

Failure Risk:
87%

Severity:
HIGH
```

---

# 14. Workflow 2: Alert Triage

When an alert is generated:

```text
Alert
 ↓
Orchestrator
 ↓
Reliability Agent
 ↓
Triage
```

The Reliability Agent determines:

```text
Is this a real anomaly?
How severe is it?
Does it require investigation?
Is there enough evidence?
```

---

# 15. Alert Triage Process

```text
1. Resolve machine

2. Validate alert

3. Check sensor health

4. Check recent telemetry

5. Compare against baseline

6. Check operating regime

7. Check duplicate alerts

8. Check asset criticality

9. Determine investigation priority
```

---

# 16. Alert Deduplication

Multiple sensor anomalies can represent the same event.

Example:

```text
Vibration ↑
Temperature ↑
Motor current ↑
```

The system should correlate them into one investigation where appropriate.

```text
Sensor Anomalies
       ↓
Correlation
       ↓
Reliability Event
       ↓
Alert
```

This prevents alert storms.

---

# 17. Alert Correlation

Correlation may consider:

```text
same machine
same component
same time window
same operating regime
related sensor types
related failure signatures
```

---

# 18. Workflow 3: Reliability Investigation

This is the central agentic workflow.

```text
Alert
 ↓
Reliability Agent
 ↓
Context Gathering
 ↓
Evidence Collection
 ↓
Hypothesis Generation
 ↓
Hypothesis Evaluation
 ↓
Finding
 ↓
Recommendation
```

---

# 19. Reliability Investigation Input

```text
alert_id
machine_id
severity
risk_score
trigger_timestamp
```

Optional:

```text
user_question
production_context
quality_context
maintenance_context
```

---

# 20. Reliability Investigation Context

The agent should retrieve:

```text
Machine
Component
Sensors
Recent Telemetry
Historical Telemetry
Baseline
Anomalies
Failure History
Maintenance History
Production Context
Quality Context
OEE Impact
Machine Manual
Maintenance Procedures
```

---

# 21. Reliability Investigation Tools

The Reliability Agent should have access to tools such as:

```text
get_machine
get_machine_health
get_recent_measurements
get_measurement_features
get_baseline
get_anomalies
get_failure_history
get_maintenance_history
get_production_context
get_quality_context
get_oee_impact
search_machine_manual
search_maintenance_procedure
```

---

# 22. Reliability Investigation Flow

```text
                Alert
                  │
                  ▼
          Resolve Machine
                  │
                  ▼
         Gather Machine State
                  │
                  ▼
         Gather Recent Signals
                  │
                  ▼
        Compare Against Baseline
                  │
                  ▼
        Inspect Historical Failures
                  │
                  ▼
       Inspect Maintenance History
                  │
                  ▼
       Inspect Production Context
                  │
                  ▼
          Search Documentation
                  │
                  ▼
          Generate Hypotheses
                  │
                  ▼
          Evaluate Evidence
                  │
                  ▼
             Finding
                  │
                  ▼
          Recommendation
```

---

# 23. Hypothesis Generation

The agent should generate a small number of candidate explanations.

Example:

```text
Hypothesis 1:
Bearing degradation

Hypothesis 2:
Misalignment

Hypothesis 3:
Temporary load-induced vibration
```

It should not generate dozens of speculative possibilities.

---

# 24. Hypothesis Evaluation

Each hypothesis should be evaluated against evidence.

Example:

| Hypothesis          | Supporting Evidence                                  | Contradicting Evidence                | Confidence |
| ------------------- | ---------------------------------------------------- | ------------------------------------- | ---------: |
| Bearing degradation | Vibration rise, temperature rise, historical failure | None significant                      |       High |
| Misalignment        | Vibration pattern                                    | No corresponding maintenance history  |     Medium |
| Temporary load      | High production load                                 | Pattern persists after load reduction |        Low |

The final output should identify the leading hypothesis without pretending certainty.

---

# 25. Evidence Model

Evidence should be structured.

Example:

```text
{
  "evidence_id": "E-001",
  "type": "TELEMETRY",
  "source": "sensor_measurement",
  "entity_id": "M204",
  "metric": "vibration_rms",
  "observed_value": 0.82,
  "baseline_value": 0.55,
  "timestamp": "...",
  "relationship": "supports"
}
```

---

# 26. Evidence Categories

Evidence can come from:

```text
TELEMETRY
MAINTENANCE
FAILURE_HISTORY
PRODUCTION
QUALITY
OEE
DOCUMENT
ASSET
OPERATING_CONTEXT
```

---

# 27. Evidence Relationships

Evidence can:

```text
SUPPORT
CONTRADICT
CORRELATE
CONFIRM
WARN
```

---

# 28. Finding

The agent converts evidence into a structured finding.

Example:

```text
Finding:

M204 shows a pattern consistent with
bearing degradation.

Confidence:
0.87

Supporting evidence:
E-001
E-004
E-007
E-009
```

---

# 29. Recommendation

The agent should then generate an operational recommendation.

Example:

```text
Recommendation:

Inspect the bearing assembly during the
next available maintenance window.

Suggested inspection:
1. Check bearing temperature.
2. Inspect vibration signature.
3. Inspect lubrication condition.
4. Check bearing wear.
```

---

# 30. Recommendation vs Action

The agent must distinguish:

```text
Recommendation
```

from:

```text
Action
```

Example:

```text
Recommendation:
Inspect bearing assembly.

Action:
Create maintenance work order.
```

The recommendation can exist without executing the action.

---

# 31. Workflow 4: Failure Prediction

Failure prediction is primarily an ML workflow.

The agent consumes model results rather than replacing the model.

```text
Telemetry
 ↓
Features
 ↓
ML Model
 ↓
Failure Risk
 ↓
Reliability Agent
```

---

# 32. Failure Prediction Output

```text
machine_id
failure_mode
risk_score
prediction_horizon
model_version
confidence
```

Example:

```text
M204

Failure Mode:
Bearing degradation

Risk:
87%

Prediction Horizon:
72 hours

Model:
bearing_risk_v3
```

---

# 33. Agent Role in Failure Prediction

The agent should:

```text
interpret prediction
validate supporting context
investigate
explain
recommend
```

It should not invent or modify the ML score.

---

# 34. Workflow 5: OEE Investigation

The OEE Agent handles questions and alerts related to Overall Equipment Effectiveness.

```text
OEE Drop
 ↓
OEE Agent
 ↓
Availability
Performance
Quality
 ↓
Identify dominant loss
 ↓
Trace to machine/process
 ↓
Investigate cause
```

---

# 35. OEE Components

```text
OEE = Availability × Performance × Quality
```

The OEE calculation itself should be deterministic.

The agent explains the result.

---

# 36. OEE Investigation Example

Input:

```text
Line A OEE:
91% → 82%
```

Agent investigates:

```text
Availability:
91% → 84%

Performance:
96% → 95%

Quality:
99% → 98%
```

The agent identifies availability as the dominant loss.

Then:

```text
Availability Loss
 ↓
Downtime
 ↓
M204
 ↓
Bearing Failure
```

---

# 37. OEE Agent Tools

```text
get_oee
get_oee_trend
get_availability_loss
get_performance_loss
get_quality_loss
get_downtime_events
get_machine_contribution
get_production_context
get_reliability_alerts
```

---

# 38. OEE Agent Output

```text
oee_investigation_id
period
line_id
oee_change
dominant_loss
contributing_assets
evidence
finding
recommendation
```

---

# 39. Workflow 6: Quality Investigation

The Quality Agent investigates sudden changes in defect rates.

Example:

```text
Defect rate:
1.2% → 4.7%
```

Flow:

```text
Quality Alert
 ↓
Quality Agent
 ↓
Identify defect type
 ↓
Identify affected products
 ↓
Identify affected machines
 ↓
Inspect process conditions
 ↓
Inspect telemetry
 ↓
Inspect maintenance
 ↓
Generate hypotheses
```

---

# 40. Quality Agent Tools

```text
get_quality_events
get_defect_trends
get_quality_measurements
get_production_runs
get_machine_context
get_process_conditions
get_maintenance_events
get_machine_health
```

---

# 41. Quality Investigation Output

```text
quality_investigation_id
defect
affected_product
affected_machine
time_window
evidence
candidate_causes
finding
recommendation
confidence
```

---

# 42. Workflow 7: Maintenance Planning

The Maintenance Agent turns recommendations into maintenance activities.

```text
Recommendation
 ↓
Maintenance Agent
 ↓
Validate asset
 ↓
Determine task
 ↓
Determine priority
 ↓
Determine required skills
 ↓
Check spare parts
 ↓
Check schedule
 ↓
Generate work order proposal
```

---

# 43. Maintenance Agent Tools

```text
get_asset
get_maintenance_history
get_open_work_orders
get_maintenance_strategy
get_required_skills
get_spare_parts
get_maintenance_schedule
create_work_order
assign_work_order
schedule_maintenance
```

---

# 44. Work Order Proposal

Before creation:

```text
Asset:
M204

Problem:
Potential bearing degradation

Priority:
High

Recommended Task:
Inspect bearing assembly

Required Skill:
Mechanical maintenance

Estimated Duration:
2 hours

Suggested Window:
Next planned maintenance window
```

---

# 45. Workflow 8: Work Order Creation

```text
Recommendation
 ↓
Action Proposal
 ↓
Policy Check
 ↓
Approval
 ↓
Create Work Order
 ↓
Verify Creation
 ↓
Audit
```

---

# 46. Work Order Policy

Example:

```text
IF
asset_criticality = LOW

AND
recommendation_confidence >= 0.90

THEN
auto_create = TRUE
```

Another:

```text
IF
asset_criticality = CRITICAL

THEN
human_approval = REQUIRED
```

The exact policies should be configurable.

---

# 47. Work Order Idempotency

Work order creation must be idempotent.

Use:

```text
idempotency_key
```

such as:

```text
asset_id
+
recommendation_id
```

If a retry occurs:

```text
Existing Work Order
 ↓
Return Existing Work Order
```

rather than creating a duplicate.

---

# 48. Workflow 9: Maintenance Verification

After a work order is completed:

```text
Work Order Completed
 ↓
Maintenance Agent
 ↓
Retrieve post-maintenance telemetry
 ↓
Compare against pre-maintenance state
 ↓
Evaluate recovery
 ↓
Close investigation
```

---

# 49. Verification Signals

For a vibration-related issue:

```text
Vibration RMS
Temperature
RPM stability
Failure risk
```

For a quality issue:

```text
Defect rate
Yield
Quality measurements
```

For OEE:

```text
Availability
Performance
Quality
OEE
```

---

# 50. Verification Output

```text
{
  "verification_status": "RECOVERED",
  "asset_id": "M204",
  "pre_maintenance_risk": 0.87,
  "post_maintenance_risk": 0.21,
  "vibration_change": "-43%",
  "oee_impact": "+4.2%",
  "confidence": 0.91
}
```

---

# 51. Verification States

```text
RECOVERED
PARTIALLY_RECOVERED
NOT_RECOVERED
INSUFFICIENT_DATA
UNKNOWN
```

---

# 52. Workflow 10: Natural Language Investigation

Users can initiate workflows through Streamlit.

Example:

```text
"Why is M204 at risk?"
```

Flow:

```text
User
 ↓
Streamlit
 ↓
Orchestrator
 ↓
Intent Classification
 ↓
Reliability Agent
 ↓
Investigation
 ↓
Response
```

---

# 53. Natural Language Intent Types

The orchestrator should classify questions into categories such as:

```text
ASSET_HEALTH
FAILURE_RISK
OEE
QUALITY
MAINTENANCE
WORK_ORDER
ALERT
PRODUCTION
KNOWLEDGE
GENERAL_ANALYTICS
```

---

# 54. Example User Questions

```text
Why is M204 at risk?

Which machines are likely to fail
within the next 72 hours?

Why did Line A OEE fall yesterday?

What caused yesterday's downtime?

Which machine contributes most to
the current availability loss?

What maintenance is due today?

Show me all high-risk assets.

Why did defect rate increase?

Create a work order for M204.
```

---

# 55. Workflow 11: Scheduled Reliability Scan

The system should periodically evaluate machine health.

Example:

```text
Every 15 minutes
```

Flow:

```text
Scheduled Trigger
 ↓
Health Evaluation
 ↓
Risk Ranking
 ↓
Threshold Check
 ↓
Alert Generation
 ↓
Agent Investigation
```

The schedule should be implemented through the appropriate Snowflake scheduling/orchestration mechanisms.

---

# 56. Scheduled OEE Scan

Example:

```text
Every hour
```

The system evaluates:

```text
OEE
Availability
Performance
Quality
Downtime
```

If material degradation is detected:

```text
OEE Alert
 ↓
OEE Agent
```

---

# 57. Workflow 12: Daily Reliability Briefing

A scheduled workflow can produce a daily operational briefing.

```text
Daily Trigger
 ↓
Orchestrator
 ↓
Reliability Agent
 ↓
OEE Agent
 ↓
Maintenance Agent
 ↓
Aggregate
 ↓
Daily Brief
```

The briefing should include:

```text
Top risks
OEE changes
Critical alerts
Open work orders
Overdue maintenance
Emerging anomalies
```

---

# 58. Workflow 13: Cross-Agent Investigation

Some problems require multiple specialists.

Example:

```text
"Why did Line A OEE drop?"
```

Orchestrator:

```text
OEE Agent
   ↓
Reliability Agent
   ↓
Quality Agent
   ↓
Maintenance Agent
```

The orchestrator combines their structured outputs.

---

# 59. Cross-Agent Context

Each agent should receive only relevant context.

Example:

```text
OEE Agent
→ OEE metrics + downtime

Reliability Agent
→ machine health + telemetry

Quality Agent
→ defect data

Maintenance Agent
→ maintenance state
```

Avoid passing the entire database or all previous context to every agent.

---

# 60. Cross-Agent Output

Each specialist returns:

```text
finding
evidence
confidence
recommendation
```

The orchestrator aggregates:

```text
overall_finding
contributing_factors
evidence
recommendations
next_action
```

---

# 61. Workflow 14: Root Cause Investigation

Root cause analysis should be evidence-driven.

```text
Problem
 ↓
Time Window
 ↓
Affected Assets
 ↓
Process Conditions
 ↓
Telemetry
 ↓
Maintenance
 ↓
Quality
 ↓
Historical Failures
 ↓
Candidate Causes
 ↓
Evidence Ranking
 ↓
Root Cause Hypothesis
```

---

# 62. Root Cause Investigation Boundaries

The agent should distinguish:

```text
Observed fact
```

from:

```text
Inference
```

Example:

```text
FACT:
Vibration increased 48%.

FACT:
Bearing inspection is overdue.

INFERENCE:
Bearing degradation is a plausible cause.

CONFIDENCE:
High.
```

---

# 63. Workflow 15: Knowledge Retrieval

When documentation is needed:

```text
Agent
 ↓
search_machine_manual()
 ↓
Document Search
 ↓
Relevant Chunks
 ↓
Metadata
 ↓
Agent Context
```

---

# 64. Knowledge Retrieval Requirements

Retrieved documents should preserve:

```text
document_id
document_version
machine_id
section
page
chunk_id
text
source
```

This enables traceability.

---

# 65. Knowledge Retrieval Example

Agent asks:

```text
"What inspection procedure should be used
for M204's bearing assembly?"
```

Search returns:

```text
Machine Manual
Section 7.2
Bearing Inspection
```

The agent can incorporate the documented procedure into its recommendation.

---

# 66. Workflow 16: Low-Confidence Investigation

If evidence is weak:

```text
Alert
 ↓
Investigation
 ↓
Insufficient Evidence
```

The agent should produce:

```text
Finding:
Unable to establish a reliable failure mode.

Missing evidence:
Recent maintenance history.

Recommendation:
Inspect maintenance records before taking action.
```

It should not fabricate a diagnosis.

---

# 67. Workflow 17: Conflicting Evidence

Example:

```text
Telemetry:
Supports bearing degradation.

Maintenance:
Bearing recently replaced.

Manual:
Current vibration pattern is expected under
high-load operation.
```

The agent should detect the conflict.

Output:

```text
Status:
CONFLICTING_EVIDENCE

Action:
Request engineering review.
```

---

# 68. Workflow 18: Missing Data

Example:

```text
Sensor unavailable
```

The workflow becomes:

```text
Risk Alert
 ↓
Sensor Health Check
 ↓
Sensor Missing
 ↓
Investigation Blocked
 ↓
Fallback Data Sources
```

Possible fallback:

```text
Maintenance history
Production context
Quality
Other sensors
```

If evidence remains insufficient:

```text
INSUFFICIENT_EVIDENCE
```

---

# 69. Workflow 19: Tool Failure

If a tool fails:

```text
Agent
 ↓
Tool Call
 ↓
Failure
 ↓
Retry if safe
 ↓
Alternative Tool
 ↓
Continue
```

If no safe fallback exists:

```text
Workflow
 ↓
BLOCKED
 ↓
Human / System Alert
```

---

# 70. Tool Retry Policy

Retries should depend on tool type.

Safe:

```text
read telemetry
read history
search documents
```

Potentially unsafe:

```text
create work order
assign technician
send notification
```

Action tools should be idempotent before automatic retry.

---

# 71. Workflow 20: Action Approval

```text
Recommendation
 ↓
Action Proposal
 ↓
Policy Evaluation
 ↓
Approval Required?
 ├── NO → Execute
 │
 └── YES
       ↓
   Human Review
       ↓
   Approve / Reject
```

---

# 72. Approval Record

Store:

```text
approval_id
action_id
requested_by
approver
requested_at
decision
decision_timestamp
reason
```

---

# 73. Rejection Flow

If rejected:

```text
Action Proposal
 ↓
Rejected
 ↓
Record Reason
 ↓
Investigation Remains Open
```

The agent should not repeatedly attempt the same rejected action.

---

# 74. Human Override

Users can override recommendations.

Example:

```text
Agent:
Inspect bearing.

Engineer:
Do not inspect bearing.
Investigate coupling first.
```

The system records:

```text
agent_recommendation
human_decision
override_reason
```

---

# 75. Workflow 21: Alert Closure

An alert can be closed when:

```text
Issue resolved
```

or:

```text
False positive
```

or:

```text
Risk returned to normal
```

or:

```text
Superseded by another investigation
```

---

# 76. Alert States

```text
NEW
TRIAGED
INVESTIGATING
ACTION_PROPOSED
AWAITING_APPROVAL
ACTION_IN_PROGRESS
RESOLVED
FALSE_POSITIVE
BLOCKED
CLOSED
```

---

# 77. Workflow 22: False Positive Learning

If an alert is marked false positive:

```text
Alert
 ↓
False Positive
 ↓
Capture reason
 ↓
Evaluate signal
 ↓
Model / rule analysis
```

Possible reasons:

```text
sensor issue
normal operating regime
temporary load
incorrect threshold
model error
```

This becomes feedback for future model improvement.

---

# 78. Workflow 23: Prediction Outcome Evaluation

When a predicted failure either occurs or does not occur:

```text
Prediction
 ↓
Prediction Horizon
 ↓
Actual Outcome
 ↓
Compare
 ↓
Metric
```

Example:

```text
Prediction:
Bearing failure risk = 87%

Actual:
Bearing failure occurred 38 hours later.
```

Outcome:

```text
TRUE_POSITIVE
```

---

# 79. Prediction Outcome States

```text
TRUE_POSITIVE
FALSE_POSITIVE
TRUE_NEGATIVE
FALSE_NEGATIVE
UNKNOWN
```

---

# 80. Workflow 24: Agent Learning

Agents should not silently modify their own behavior in production.

Instead:

```text
Outcome
 ↓
Evaluation
 ↓
Dataset
 ↓
Human / Engineering Review
 ↓
Model / Prompt / Tool Improvement
 ↓
Testing
 ↓
Deployment
```

This preserves governance.

---

# 81. Agent Memory

Agent memory should be divided into:

## Operational State

Stored in Snowflake.

Examples:

```text
investigation
recommendation
work order
approval
```

## Conversational Context

Used for the current interaction.

## Historical Knowledge

Stored in governed data and knowledge systems.

The LLM's context should never become the authoritative system of record.

---

# 82. Agent Context Construction

Before reasoning, the system should construct a bounded context:

```text
Asset Context
+
Alert Context
+
Telemetry Context
+
Maintenance Context
+
Production Context
+
Quality Context
+
Knowledge Context
```

Only relevant information should be passed to the agent.

---

# 83. Context Priority

Recommended priority:

```text
1. Current event
2. Current asset state
3. Recent telemetry
4. Historical evidence
5. Maintenance context
6. Production context
7. Quality context
8. Documentation
9. Broader historical context
```

---

# 84. Context Freshness

Different data has different freshness requirements.

Example:

```text
Telemetry:
minutes

Machine health:
minutes

Maintenance:
hours/days

Asset metadata:
days

Machine manuals:
weeks/months
```

Agents should know the freshness of evidence.

---

# 85. Agent Confidence

Confidence should not be treated as a magical number generated by the LLM.

Confidence should be supported by evidence.

Possible factors:

```text
evidence_count
evidence_quality
model_confidence
data_freshness
historical_match
contradictions
```

---

# 86. Confidence Levels

The UI can expose:

```text
HIGH
MEDIUM
LOW
```

Internally, structured numerical values may also be stored.

---

# 87. Confidence Policy

Example:

```text
HIGH
→ recommendation allowed

MEDIUM
→ human review recommended

LOW
→ investigation only
```

Policies should be configurable.

---

# 88. Agent Tool Selection

The agent should use the smallest number of tools necessary.

Example:

User:

```text
"Why is M204 at risk?"
```

Likely tools:

```text
get_machine_health
get_recent_measurements
get_failure_history
get_maintenance_history
search_machine_manual
```

It should not call:

```text
get_all_factory_data
```

---

# 89. Tool Permissions

Each agent receives a capability set.

Example:

## Reliability Agent

```text
READ:
telemetry
maintenance
failure
production
quality
knowledge

WRITE:
investigation
recommendation
```

No direct work order creation unless explicitly permitted by workflow.

---

# 90. Maintenance Agent Permissions

```text
READ:
asset
maintenance
inventory
schedule

WRITE:
work_order
maintenance_plan
assignment
```

Subject to policy.

---

# 91. Orchestrator Permissions

The orchestrator should coordinate.

It should not become a universal database-writing agent.

Preferred:

```text
Orchestrator
→ delegates
→ aggregates
→ routes
```

---

# 92. Agent Handoff

Handoffs should be structured.

Example:

```text
Reliability Agent
        ↓
{
  "asset_id": "M204",
  "finding": "Bearing degradation likely",
  "confidence": 0.87,
  "recommendation_id": "REC-204"
}
        ↓
Maintenance Agent
```

---

# 93. Handoff Validation

Before another agent receives the result:

```text
Schema validation
 ↓
Required fields
 ↓
Entity validation
 ↓
Confidence validation
```

If invalid:

```text
Reject handoff
```

---

# 94. Agent-to-Agent Communication

Agents should not rely on conversational prose alone.

Use structured workflow state.

Bad:

```text
"Hey Maintenance Agent, I think maybe M204
has some bearing issue..."
```

Preferred:

```text
{
  "asset_id": "M204",
  "failure_mode": "BEARING_DEGRADATION",
  "confidence": 0.87,
  "recommendation": "INSPECT_BEARING"
}
```

---

# 95. Orchestration Patterns

The system supports:

### Sequential

```text
A → B → C
```

### Parallel

```text
       ┌→ A ─┐
Start ─┼→ B ─┼→ Aggregate
       └→ C ─┘
```

### Conditional

```text
IF risk > threshold
    → investigation
ELSE
    → monitor
```

### Human-in-loop

```text
Agent
 ↓
Approval
 ↓
Continue
```

---

# 96. Parallel Investigation

Example:

```text
OEE Agent
   │
   ├── Reliability Agent
   │
   └── Quality Agent
```

Both can investigate independently.

The Orchestrator aggregates the results.

---

# 97. Conditional Investigation

Example:

```text
IF
failure_risk >= 0.80

THEN
investigate

ELSE
monitor
```

This avoids unnecessary agent execution.

---

# 98. Escalation Workflow

If an agent cannot resolve an issue:

```text
Agent
 ↓
Low Confidence / Conflict
 ↓
Escalation
 ↓
Human Engineer
```

The escalation should contain:

```text
problem
evidence
unknowns
tools attempted
recommendation
```

---

# 99. Agent Response Structure

Every user-facing investigation should conceptually follow:

```text
SUMMARY

WHAT HAPPENED

EVIDENCE

LIKELY CAUSE

CONFIDENCE

RECOMMENDATION

ACTION

NEXT STEP
```

---

# 100. Example User-Facing Response

```text
M204 is showing elevated bearing-failure risk.

Risk:
87%

Why:
• Vibration RMS is 48% above its operating baseline.
• Temperature has increased continuously over the last 6 hours.
• Similar telemetry preceded two historical bearing failures.
• The last bearing inspection occurred 147 days ago.

Finding:
Bearing degradation is the leading hypothesis.

Confidence:
High

Recommendation:
Inspect the bearing assembly during the next maintenance window.

Action:
A work-order proposal is ready for review.
```

---

# 101. Agent Activity in the Command Center

The UI should expose an agent activity timeline.

Example:

```text
10:14
Alert detected

10:15
Reliability Agent started

10:15
Telemetry retrieved

10:15
Maintenance history retrieved

10:16
Failure history retrieved

10:16
Machine manual searched

10:16
Investigation completed

10:16
Recommendation generated

10:17
Approval requested
```

This gives operators visibility without exposing private chain-of-thought.

---

# 102. Agent Audit Trail

Every execution should be traceable.

Example:

```text
Investigation:
INV-2026-00042

Agent:
ReliabilityAgent

Trigger:
ALT-8821

Tools:
get_machine_health
get_recent_measurements
get_failure_history
get_maintenance_history
search_machine_manual

Finding:
Bearing degradation

Recommendation:
Inspect bearing

Confidence:
0.87
```

---

# 103. Workflow Observability

Track:

```text
workflow_count
success_rate
failure_rate
average_latency
tool_failure_rate
human_approval_rate
human_override_rate
recommendation_acceptance_rate
```

---

# 104. Agent Cost Observability

Track:

```text
agent executions
tool calls
token usage where available
execution duration
retries
```

This helps prevent unnecessary agent invocations.

---

# 105. Agent Trigger Optimization

Not every anomaly should invoke an LLM.

Use a funnel:

```text
All telemetry
     ↓
Deterministic anomaly detection
     ↓
Risk threshold
     ↓
Alert filtering
     ↓
Agent investigation
```

This keeps the agent layer focused.

---

# 106. Recommended Trigger Strategy

```text
Telemetry:
Millions of records

↓

SQL / ML:
Thousands of evaluated signals

↓

Alerts:
Dozens

↓

Agent investigations:
Only meaningful alerts

↓

Human actions:
Small number of consequential events
```

This is the economically sensible architecture.

---

# 107. Agent Workflow State Machine

The reliability investigation can be represented as:

```text
                  ┌───────────┐
                  │   NEW     │
                  └─────┬─────┘
                        │
                        ▼
                  ┌───────────┐
                  │  TRIAGED  │
                  └─────┬─────┘
                        │
                        ▼
                ┌────────────────┐
                │ INVESTIGATING  │
                └───────┬────────┘
                        │
             ┌──────────┼──────────┐
             │          │          │
             ▼          ▼          ▼
          BLOCKED     FINDING   LOW_CONFIDENCE
             │          │          │
             │          ▼          │
             │    RECOMMENDATION  │
             │          │          │
             │          ▼          │
             │    ACTION_PROPOSED │
             │          │          │
             │          ▼          │
             │   AWAITING_APPROVAL│
             │          │          │
             │          ▼          │
             │   ACTION_IN_PROGRESS
             │          │
             │          ▼
             │       RESOLVED
             │          │
             └──────────┴──────────┘
                        │
                        ▼
                      CLOSED
```

---

# 108. Agent Workflow Data Model

Recommended operational entities:

```text
agent
agent_execution
agent_trigger
agent_context
tool
tool_call
evidence
hypothesis
finding
recommendation
action
approval
execution_result
verification
```

These entities should align with the platform ontology.

---

# 109. Tool Call Record

Every tool call should record:

```text
tool_call_id
agent_execution_id
tool_name
arguments
started_at
completed_at
status
result
error
```

Sensitive arguments should be governed appropriately.

---

# 110. Evidence Record

```text
evidence_id
investigation_id
source_type
source_id
entity_id
observation
timestamp
relationship
strength
```

---

# 111. Hypothesis Record

```text
hypothesis_id
investigation_id
failure_mode
supporting_evidence
contradicting_evidence
confidence
status
```

---

# 112. Recommendation Record

```text
recommendation_id
investigation_id
recommendation_type
description
priority
confidence
required_skill
estimated_duration
```

---

# 113. Action Record

```text
action_id
recommendation_id
action_type
status
policy_result
approval_required
approved_by
executed_at
external_reference
```

---

# 114. Verification Record

```text
verification_id
action_id
verification_type
before_state
after_state
outcome
confidence
verified_at
```

---

# 115. Complete Reliability Workflow

The canonical reliability workflow is:

```text
┌────────────────────────────────────────────┐
│                TELEMETRY                   │
└──────────────────┬─────────────────────────┘
                   ↓
┌────────────────────────────────────────────┐
│        FEATURE / ANOMALY PIPELINE          │
└──────────────────┬─────────────────────────┘
                   ↓
┌────────────────────────────────────────────┐
│             FAILURE RISK MODEL             │
└──────────────────┬─────────────────────────┘
                   ↓
┌────────────────────────────────────────────┐
│                   ALERT                    │
└──────────────────┬─────────────────────────┘
                   ↓
┌────────────────────────────────────────────┐
│             ORCHESTRATOR AGENT             │
└──────────────────┬─────────────────────────┘
                   ↓
┌────────────────────────────────────────────┐
│            RELIABILITY AGENT               │
│                                            │
│ Telemetry                                 │
│ Maintenance                               │
│ Failure History                            │
│ Production                                │
│ Quality                                   │
│ Knowledge                                 │
└──────────────────┬─────────────────────────┘
                   ↓
┌────────────────────────────────────────────┐
│                 FINDING                    │
└──────────────────┬─────────────────────────┘
                   ↓
┌────────────────────────────────────────────┐
│              RECOMMENDATION                │
└──────────────────┬─────────────────────────┘
                   ↓
┌────────────────────────────────────────────┐
│              POLICY ENGINE                 │
└──────────────────┬─────────────────────────┘
                   ↓
             Approval Required?
                /       \
              YES        NO
               ↓          ↓
          Human Review   Execute
               │          │
               └────┬─────┘
                    ↓
┌────────────────────────────────────────────┐
│             MAINTENANCE AGENT              │
└──────────────────┬─────────────────────────┘
                   ↓
┌────────────────────────────────────────────┐
│               WORK ORDER                   │
└──────────────────┬─────────────────────────┘
                   ↓
┌────────────────────────────────────────────┐
│              MAINTENANCE                   │
└──────────────────┬─────────────────────────┘
                   ↓
┌────────────────────────────────────────────┐
│              VERIFICATION                  │
└──────────────────┬─────────────────────────┘
                   ↓
┌────────────────────────────────────────────┐
│                OUTCOME                     │
└──────────────────┬─────────────────────────┘
                   ↓
┌────────────────────────────────────────────┐
│          LEARNING / EVALUATION             │
└──────────────────┬─────────────────────────┘
                   │
                   └────────────→ SNOWFLAKE
```

---

# 116. Complete OEE Workflow

```text
Production Data
       ↓
OEE Calculation
       ↓
OEE Trend
       ↓
Deviation Detection
       ↓
OEE Alert
       ↓
OEE Agent
       ↓
Availability / Performance / Quality
       ↓
Loss Attribution
       ↓
Machine / Process Attribution
       ↓
Reliability / Quality Investigation
       ↓
Finding
       ↓
Recommendation
       ↓
Action
       ↓
Verification
```

---

# 117. Complete Quality Workflow

```text
Quality Measurements
       ↓
Defect Detection
       ↓
Defect Rate Change
       ↓
Quality Alert
       ↓
Quality Agent
       ↓
Affected Product
       ↓
Affected Process
       ↓
Affected Machine
       ↓
Telemetry Correlation
       ↓
Maintenance Correlation
       ↓
Candidate Causes
       ↓
Recommendation
```

---

# 118. Complete Natural Language Workflow

```text
User
 ↓
Streamlit
 ↓
Orchestrator
 ↓
Intent
 ↓
Relevant Agent
 ↓
Semantic Layer
 ↓
Tools
 ↓
Evidence
 ↓
Finding
 ↓
Response
```

If the user asks for an action:

```text
User
 ↓
Orchestrator
 ↓
Relevant Agent
 ↓
Recommendation
 ↓
Policy
 ↓
Approval
 ↓
Tool
 ↓
Action
 ↓
Result
```

---

# 119. Complete Daily Operations Workflow

```text
                    DAILY START
                         │
                         ▼
              Factory Health Scan
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
          Reliability   OEE       Quality
              │          │          │
              └──────────┼──────────┘
                         ▼
                    Orchestrator
                         │
                         ▼
                  Daily Briefing
                         │
                         ▼
                    Command Center
                         │
                         ▼
                  Human Decisions
                         │
                         ▼
                    Maintenance
                         │
                         ▼
                    Verification
```

---

# 120. CoCo and Agent Workflows

CoCo should be visible across the lifecycle.

## Planning

Use CoCo to:

```text
inspect schemas
understand data
draft workflows
design tools
design agents
generate test scenarios
```

## Development

Use CoCo to:

```text
create SQL
create pipelines
create semantic definitions
build agent workflows
create tools
build Streamlit components
write tests
```

## Execution

Use CoCo to:

```text
run workflows
execute pipelines
test agents
run validations
inspect failures
```

## Testing

Use CoCo to:

```text
generate test data
run scenarios
validate outputs
test edge cases
inspect errors
```

---

# 121. CoCo Development Workflow

The development loop should look like:

```text
Developer
    ↓
CoCo
    ↓
Inspect Repository
    ↓
Inspect Snowflake
    ↓
Implement
    ↓
Run
    ↓
Test
    ↓
Observe
    ↓
Fix
    ↓
Commit
```

This should be demonstrable during the project.

---

# 122. Reusable CoCo Skills

The project should create reusable skills around common workflows.

Potential skills:

```text
reliability-investigation
oee-investigation
quality-investigation
asset-health-analysis
maintenance-planning
work-order-validation
agent-evaluation
factory-data-generation
```

---

# 123. Reliability Investigation Skill

A reusable skill should encapsulate:

```text
retrieve asset
retrieve telemetry
retrieve baseline
retrieve maintenance
retrieve failures
retrieve production
retrieve quality
search documents
evaluate hypotheses
produce finding
```

This creates a reusable reliability capability.

---

# 124. Agent Evaluation Skill

A reusable skill can execute:

```text
scenario
 ↓
agent
 ↓
expected output
 ↓
actual output
 ↓
evaluation
```

Metrics:

```text
correctness
groundedness
tool selection
action safety
confidence calibration
```

---

# 125. Synthetic Scenario Skill

CoCo can generate consistent scenarios such as:

```text
normal operation
bearing degradation
motor overheating
misalignment
lubrication failure
quality drift
unexpected downtime
sensor failure
```

Each scenario should produce:

```text
telemetry
maintenance history
failure event
production impact
quality impact
```

---

# 126. Canonical Demo Agent Workflow

The primary product demonstration should use this exact sequence:

```text
1. M204 operates normally.

2. Synthetic telemetry begins drifting.

3. Snowflake pipeline processes new telemetry.

4. Anomaly detection identifies abnormal vibration.

5. Failure model increases risk.

6. Alert appears in Streamlit.

7. Reliability Agent is triggered.

8. Agent gathers machine context.

9. Agent retrieves recent telemetry.

10. Agent compares against baseline.

11. Agent checks historical failures.

12. Agent checks maintenance history.

13. Agent searches machine documentation.

14. Agent produces evidence.

15. Agent identifies bearing degradation
    as the leading hypothesis.

16. Agent produces a recommendation.

17. Maintenance Agent prepares work-order proposal.

18. Policy determines approval is required.

19. Reliability Engineer approves.

20. Work order is created.

21. Maintenance event is simulated.

22. Post-maintenance telemetry improves.

23. Verification Agent/Workflow confirms recovery.

24. Risk score decreases.

25. OEE improves.

26. Investigation is closed.

27. Outcome is stored.

28. Prediction outcome becomes evaluation data.
```

---

# 127. What Makes This Agentic

The system is genuinely agentic when it can:

```text
Observe
   ↓
Choose what information it needs
   ↓
Choose tools
   ↓
Investigate
   ↓
Reason over multiple sources
   ↓
Produce a recommendation
   ↓
Choose whether an action is appropriate
   ↓
Call an action tool
   ↓
Observe the result
   ↓
Continue or escalate
```

It is not sufficient to have:

```text
Dashboard
+
Chatbot
```

The agent must participate in the operational workflow.

---

# 128. What Should NOT Be Agentic

Avoid using agents for tasks that are better handled deterministically.

Do not use an LLM for:

```text
OEE arithmetic
rolling averages
simple aggregations
data cleaning
primary key validation
threshold comparisons
basic joins
timestamp normalization
```

Use:

```text
SQL
Snowflake pipelines
ML
deterministic code
```

instead.

---

# 129. Agentic Boundary

The ideal boundary is:

```text
                DETERMINISTIC
                     │
                     ▼
              Data Processing
                     │
                     ▼
                ML / Rules
                     │
                     ▼
                 ALERT
                     │
                     ▼
                  AGENT
                     │
                     ▼
              INVESTIGATION
                     │
                     ▼
              RECOMMENDATION
                     │
                     ▼
               POLICY ENGINE
                     │
                     ▼
                  ACTION
```

This keeps the system both intelligent and controllable.

---

# 130. Final Agentic Architecture

The complete agentic system can be summarized as:

```text
                         USER
                           │
                           ▼
                     STREAMLIT UI
                           │
                           ▼
                   ORCHESTRATOR AGENT
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
   RELIABILITY           OEE              QUALITY
      AGENT              AGENT              AGENT
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                           ▼
                   MAINTENANCE AGENT
                           │
                           ▼
                      TOOL LAYER
                           │
          ┌────────────────┼─────────────────┐
          │                │                 │
          ▼                ▼                 ▼
      Snowflake          Knowledge          MCP
      Read Tools         Search             Tools
          │                                  │
          └────────────────┬─────────────────┘
                           ▼
                     POLICY ENGINE
                           │
                     ┌─────┴─────┐
                     ▼           ▼
                  APPROVAL     EXECUTION
                     │           │
                     └─────┬─────┘
                           ▼
                    WORK ORDER / ACTION
                           │
                           ▼
                       REAL WORLD
                           │
                           ▼
                      NEW DATA
                           │
                           ▼
                      SNOWFLAKE
                           │
                           └──────────→ NEXT WORKFLOW
```

---

# 131. Final Design Principles

The agentic system must preserve the following principles:

### 1. Snowflake is the source of truth.

### 2. Agents reason over governed data.

### 3. Agents use tools rather than arbitrary database access.

### 4. Deterministic computation remains deterministic.

### 5. ML predicts; agents investigate.

### 6. Recommendations are distinct from actions.

### 7. Consequential actions are governed by policy.

### 8. Humans remain in control of high-impact decisions.

### 9. Every operational action is auditable.

### 10. Every important conclusion is evidence-backed.

### 11. Agents fail safely when evidence is insufficient.

### 12. Agent state is persisted outside the model context.

### 13. Agent-to-agent communication is structured.

### 14. Workflows are idempotent.

### 15. Outcomes are verified.

### 16. Outcomes feed model and workflow evaluation.

### 17. CoCo is used throughout planning, development, execution, and testing.

### 18. The system should remain useful even when AI capabilities are unavailable.

---

# 132. The One-Line Mental Model

The entire agentic architecture can be remembered as:

```text
DATA → SIGNAL → ALERT → AGENT → EVIDENCE → DECISION → ACTION → OUTCOME → LEARNING
```

Or, operationally:

```text
See it.
Understand it.
Predict it.
Investigate it.
Act on it.
Prove it worked.
Learn from it.
```

That is the core agent workflow of the Factory Reliability Command Center.
