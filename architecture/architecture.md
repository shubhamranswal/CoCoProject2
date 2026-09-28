# Factory Reliability Command Center

# System Architecture

**Document:** `architecture.md`
**Version:** 1.0
**Status:** Foundational Architecture
**Product:** Predictive Maintenance & OEE Command Center
**Primary Platform:** Snowflake
**Application:** Streamlit
**AI Development & Execution Surface:** Snowflake CoCo
**Architecture Style:** Data-centric, agentic, event-driven, governed

---

# 1. Architecture Overview

The Factory Reliability Command Center is an industrial intelligence platform that converges:

* OT sensor telemetry
* machine and asset hierarchy
* production data
* quality data
* maintenance history
* ERP / CMMS records
* engineering documentation
* reliability models
* AI agents
* operational actions

into a unified system for detecting, investigating, predicting, and acting on equipment reliability problems.

The platform is designed around one core principle:

> **Snowflake is the governed operational data and intelligence platform, while the agentic layer turns that data into investigation and action.**

The system is not simply a dashboard.

It is a closed-loop reliability system:

```text
                    ┌─────────────────────────┐
                    │      Factory / OT       │
                    │                         │
                    │ Sensors / PLC / SCADA   │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │      Data Ingestion     │
                    │                         │
                    │ Streams / Files / APIs  │
                    └────────────┬────────────┘
                                 │
                                 ▼
              ┌─────────────────────────────────────┐
              │             SNOWFLAKE               │
              │                                     │
              │ Raw → Core → Analytics → Semantic  │
              │                                     │
              │ Telemetry / Production / Quality   │
              │ Maintenance / Knowledge / OEE      │
              └────────────────┬────────────────────┘
                               │
                 ┌─────────────┼─────────────┐
                 │             │             │
                 ▼             ▼             ▼
             Analytics       ML Models    Semantic Layer
                 │             │             │
                 └─────────────┼─────────────┘
                               │
                               ▼
                    ┌─────────────────────────┐
                    │      Agentic Layer      │
                    │                         │
                    │ Orchestrator Agent      │
                    │ Reliability Agent       │
                    │ OEE Agent               │
                    │ Maintenance Agent       │
                    │ Quality Agent           │
                    └────────────┬────────────┘
                                 │
                   ┌─────────────┼──────────────┐
                   │             │              │
                   ▼             ▼              ▼
               Knowledge       Tools         Policies
                   │             │              │
                   └─────────────┼──────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │     Action Layer        │
                    │                         │
                    │ Work Orders             │
                    │ Notifications           │
                    │ Approvals               │
                    │ External Systems        │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │    Human / Technician   │
                    │                         │
                    │ Inspect → Repair → Test │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │      Verification       │
                    │                         │
                    │ Health / OEE / Quality  │
                    └────────────┬────────────┘
                                 │
                                 └──────────→ Feedback Loop
```

---

# 2. Product Philosophy

The system follows six architectural principles.

## 2.1 Data First

AI does not become the system of record.

Snowflake remains the governed source of truth for operational data.

---

## 2.2 Agents Reason Over Context

Agents should not operate on isolated sensor values.

They reason over:

```text
Telemetry
+
Asset context
+
Production context
+
Quality context
+
Maintenance history
+
Failure history
+
Engineering knowledge
```

---

## 2.3 Read and Write Are Separate

Reading data is fundamentally different from taking an operational action.

Therefore:

```text
READ
  ↓
REASON
  ↓
RECOMMEND
  ↓
APPROVE
  ↓
ACT
```

Actions require explicit tool permissions and policy checks.

---

## 2.4 Evidence Before Action

An agent should not create a work order simply because an ML score is high.

The system should establish:

```text
Signal
→ Anomaly
→ Evidence
→ Finding
→ Recommendation
→ Action
```

---

## 2.5 Human-in-the-Loop for Consequential Actions

The platform should automate investigation aggressively while keeping appropriate controls around consequential actions.

For example:

```text
Create investigation
        ↓
Automatically

Generate recommendation
        ↓
Automatically

Create work order
        ↓
Policy dependent

Change machine configuration
        ↓
Human approval required
```

---

## 2.6 Closed Loop

The system must measure whether recommendations actually worked.

```text
Prediction
→ Action
→ Maintenance
→ Recovery
→ Verification
→ Outcome
```

This transforms the platform from an alerting system into a learning reliability system.

---

# 3. Architecture Layers

The platform consists of ten major layers.

```text
┌─────────────────────────────────────────────────────┐
│ 10. EXPERIENCE                                      │
│ Streamlit / Command Center / Natural Language      │
├─────────────────────────────────────────────────────┤
│ 9. ACTION & INTEGRATION                             │
│ Work Orders / CMMS / ERP / Slack / Notifications   │
├─────────────────────────────────────────────────────┤
│ 8. AGENTIC INTELLIGENCE                             │
│ Orchestrator / Reliability / OEE / Maintenance     │
├─────────────────────────────────────────────────────┤
│ 7. KNOWLEDGE                                        │
│ Manuals / Procedures / Documents / Search          │
├─────────────────────────────────────────────────────┤
│ 6. SEMANTIC & ONTOLOGY                              │
│ Semantic Views / Business Entities / Relationships │
├─────────────────────────────────────────────────────┤
│ 5. ML & ANALYTICS                                   │
│ Anomaly / Prediction / OEE / RCA                    │
├─────────────────────────────────────────────────────┤
│ 4. CURATED DATA                                     │
│ Asset / Telemetry / Production / Quality / Maint.  │
├─────────────────────────────────────────────────────┤
│ 3. DATA PROCESSING                                  │
│ Streams / Tasks / Dynamic Tables / SQL             │
├─────────────────────────────────────────────────────┤
│ 2. INGESTION                                        │
│ OT / ERP / CMMS / Files / APIs                     │
├─────────────────────────────────────────────────────┤
│ 1. SOURCE SYSTEMS                                   │
│ Factory / ERP / CMMS / Documents                   │
└─────────────────────────────────────────────────────┘
```

Cross-cutting all layers:

```text
Security
Governance
Observability
Auditability
Data Quality
CoCo
```

---

# 4. High-Level Technology Stack

## Core Platform

| Layer                  | Technology                                  |
| ---------------------- | ------------------------------------------- |
| Data platform          | Snowflake                                   |
| Data transformation    | Snowflake SQL                               |
| Incremental processing | Streams / Tasks / Dynamic Tables            |
| Semantic layer         | Snowflake semantic modeling                 |
| AI development         | Snowflake CoCo                              |
| AI orchestration       | Agentic layer / Snowflake AI capabilities   |
| ML                     | Snowflake ML / Python where required        |
| Knowledge              | Snowflake document processing / search      |
| Application            | Streamlit                                   |
| External integrations  | MCP / APIs                                  |
| Work management        | CMMS / ERP integration                      |
| Notifications          | Slack / email / external notification tools |
| Source control         | Git                                         |
| Development            | CoCo CLI / Desktop                          |
| Testing                | SQL / Python / agent evaluation             |
| Authentication         | Snowflake / enterprise identity             |
| Observability          | Snowflake telemetry + application logging   |

The exact implementation can evolve, but the architectural boundaries should remain stable.

---

# 5. Role of Snowflake

Snowflake is the center of the architecture.

It should own:

```text
Operational data
Historical data
Telemetry
Asset context
Maintenance data
Production data
Quality data
OEE calculations
ML features
Model outputs
Semantic representations
Investigation evidence
Agent state
Audit records
```

Snowflake should not merely be treated as:

```text
"the database behind the dashboard"
```

It is the platform on which the intelligence system operates.

---

# 6. Role of CoCo

CoCo is the AI-native development and operational interface around the Snowflake-centric system.

The architecture should explicitly demonstrate CoCo across four lifecycle stages:

```text
PLAN
 ↓
BUILD
 ↓
RUN
 ↓
VALIDATE
```

---

# 7. CoCo in Planning

Before implementation:

```text
CoCo
 ↓
Inspect project
 ↓
Inspect available data
 ↓
Understand schema
 ↓
Frame reliability problem
 ↓
Design ontology
 ↓
Design data model
 ↓
Design agent workflow
 ↓
Generate implementation plan
```

CoCo should be used to produce:

* architecture decisions
* data model drafts
* ontology
* pipeline plan
* semantic model plan
* agent design
* testing strategy

This provides visible evidence of CoCo usage during the planning phase.

---

# 8. CoCo in Development

CoCo should be used to build the system rather than simply asking it questions about completed code.

Example:

```text
Developer
   ↓
CoCo
   ↓
Inspect repository
   ↓
Modify SQL
   ↓
Create Snowflake objects
   ↓
Create pipelines
   ↓
Create semantic definitions
   ↓
Create agents/tools
   ↓
Create Streamlit application
   ↓
Create tests
```

The repository remains version-controlled.

CoCo becomes the engineering interface through which the team builds and iterates on the repository.

---

# 9. CoCo in Execution

CoCo should be able to execute or orchestrate development and operational workflows.

Examples:

```text
Run data pipeline
Run anomaly detection
Run reliability investigation
Run agent workflow
Validate generated SQL
Run application tests
Execute scheduled workflows
```

For production execution, operational scheduling should remain governed and observable.

---

# 10. CoCo in Testing

CoCo should be used to:

```text
Inspect failures
Generate test cases
Run SQL validation
Test semantic questions
Test agent reasoning
Test tool calls
Test guardrails
Test failure scenarios
Compare expected vs actual results
```

Example:

```text
"Create a test where vibration increases,
temperature remains stable, and no maintenance
history exists."
```

The system should validate that the agent does not falsely conclude a bearing failure.

---

# 11. Data Architecture

The data architecture follows:

```text
SOURCE
   ↓
RAW
   ↓
STANDARDIZED
   ↓
CURATED
   ↓
FEATURE
   ↓
SEMANTIC
   ↓
INTELLIGENCE
```

---

# 12. Source Systems

The initial product supports simulated or real representations of:

## OT

```text
Sensors
PLC
SCADA
Historian
IoT gateways
```

## Enterprise

```text
ERP
CMMS
MES
```

## Quality

```text
Quality Management System
Inspection System
Laboratory System
```

## Knowledge

```text
Machine manuals
Maintenance procedures
Engineering documents
SOPs
Failure guides
```

---

# 13. Synthetic Data Architecture

For the initial implementation, synthetic data should be generated.

The synthetic environment should maintain referential integrity.

Example:

```text
Plant
 ↓
Line
 ↓
Machine
 ↓
Component
 ↓
Sensor
 ↓
Measurement
```

Synthetic events must connect back to the same entities.

For example:

```text
Machine M204
```

must have consistent references across:

```text
Telemetry
Production
Maintenance
Failures
Work Orders
OEE
```

---

# 14. Synthetic Failure Scenarios

Synthetic data should contain deliberately generated failure signatures.

Example:

## Bearing Degradation

```text
Vibration RMS
    ↑

Vibration Peak
    ↑

Temperature
    ↑

RPM Stability
    ↓
```

Then:

```text
Failure
    ↓
Downtime
    ↓
Maintenance
```

Historical instances should be generated so the system can compare current behavior against previous failures.

---

# 15. Data Ingestion Architecture

The ingestion layer supports:

```text
Batch
Near-real-time
Event-driven
Document ingestion
API ingestion
```

---

# 16. OT Telemetry Flow

```text
Sensor
 ↓
OT Gateway
 ↓
Streaming / Ingestion
 ↓
Snowflake RAW
 ↓
Transformation
 ↓
TELEMETRY.MEASUREMENT
```

The initial hackathon/product prototype can simulate this with generated timestamped records.

The architecture should still preserve the production shape.

---

# 17. ERP / CMMS Flow

```text
ERP / CMMS
      ↓
Connector / API
      ↓
RAW
      ↓
Standardization
      ↓
Maintenance Domain
```

The canonical ontology remains independent of the source system.

---

# 18. Document Flow

```text
Manual / SOP / Guide
        ↓
Document Ingestion
        ↓
Extraction
        ↓
Chunking
        ↓
Metadata
        ↓
Search / Retrieval
        ↓
Reliability Agent
```

Each chunk should preserve source metadata.

---

# 19. Snowflake Data Layers

Recommended logical structure:

```text
FACTORY_RAW
FACTORY_CORE
FACTORY_TELEMETRY
FACTORY_PRODUCTION
FACTORY_QUALITY
FACTORY_MAINTENANCE
FACTORY_RELIABILITY
FACTORY_KNOWLEDGE
FACTORY_INTELLIGENCE
FACTORY_AGENT
FACTORY_AUDIT
```

---

# 20. RAW Layer

Contains source-aligned data.

Examples:

```text
raw_sensor_measurements
raw_machine_assets
raw_work_orders
raw_maintenance_events
raw_production_runs
raw_quality_events
raw_documents
```

Rules:

* preserve source data
* avoid destructive transformations
* retain source identifiers
* retain ingestion metadata

---

# 21. CORE Layer

Canonical entities.

Examples:

```text
machine
component
sensor
production_line
product
technician
```

This layer implements the physical representation of the ontology's core entities.

---

# 22. TELEMETRY Layer

Contains:

```text
measurement
signal
feature
baseline
operating_regime
anomaly
```

---

# 23. PRODUCTION Layer

Contains:

```text
production_order
production_run
operation
cycle
downtime_event
```

---

# 24. QUALITY Layer

Contains:

```text
quality_inspection
quality_measurement
defect
quality_event
```

---

# 25. MAINTENANCE Layer

Contains:

```text
maintenance_strategy
maintenance_task
maintenance_event
work_order
technician
spare_part
```

---

# 26. RELIABILITY Layer

Contains:

```text
failure
failure_mode
failure_cause
failure_effect
failure_signature
failure_risk
health_assessment
prediction
```

---

# 27. KNOWLEDGE Layer

Contains:

```text
document
document_version
knowledge_chunk
knowledge_metadata
knowledge_relationship
```

---

# 28. INTELLIGENCE Layer

Contains:

```text
alert
investigation
evidence
hypothesis
finding
recommendation
confidence
```

---

# 29. AGENT Layer

Contains operational agent state.

Examples:

```text
agent
agent_execution
tool
tool_call
agent_decision
action
approval
execution
outcome
```

---

# 30. AUDIT Layer

Contains:

```text
audit_event
agent_audit
action_audit
data_access_audit
```

---

# 31. Processing Architecture

The processing architecture should be incremental.

```text
New Telemetry
     ↓
Stream
     ↓
Transformation
     ↓
Feature Calculation
     ↓
Anomaly Detection
     ↓
Risk Scoring
```

For batch or slowly changing data:

```text
Source
 ↓
Dynamic Table / Task
 ↓
Curated Table
```

---

# 32. Streams

Streams capture changes in source data.

Example:

```text
RAW_SENSOR_MEASUREMENTS
        ↓
STREAM_SENSOR_MEASUREMENTS
```

The stream identifies newly arrived or changed records.

---

# 33. Tasks

Tasks execute scheduled or dependency-driven transformations.

Example:

```text
Task:
calculate_sensor_features

Task:
detect_anomalies

Task:
calculate_failure_risk

Task:
refresh_oee
```

---

# 34. Dynamic Tables

Dynamic tables may be used where continuous transformation is appropriate.

Example:

```text
RAW_MEASUREMENTS
       ↓
Dynamic Table
       ↓
FEATURES
```

They reduce the amount of manually managed orchestration.

---

# 35. Reliability Processing Pipeline

The core reliability pipeline is:

```text
Measurements
      ↓
Cleaning
      ↓
Feature Engineering
      ↓
Baseline Comparison
      ↓
Anomaly Detection
      ↓
Failure Risk Model
      ↓
Alert Generation
```

---

# 36. Feature Engineering

Features should include:

### Statistical

```text
mean
median
standard deviation
variance
min
max
percentiles
```

### Temporal

```text
rolling_mean
rolling_std
slope
trend
rate_of_change
```

### Domain-specific

```text
vibration_rms
vibration_peak
crest_factor
temperature_delta
rpm_variance
pressure_variance
```

---

# 37. Baseline Architecture

The baseline engine should consider context.

Baseline should be calculated by combinations such as:

```text
Machine
+
Operating Regime
+
Product
+
Load
+
Time
```

Instead of assuming one universal threshold.

---

# 38. Anomaly Detection

The system may use a combination of:

```text
Rule-based detection
Statistical detection
ML anomaly detection
Domain thresholds
```

Example:

```text
IF
vibration_rms > baseline * 1.40

THEN
anomaly_score ↑
```

This is complementary to ML rather than replacing it.

---

# 39. Failure Prediction

Failure prediction combines:

```text
Current telemetry
Historical failures
Maintenance history
Asset age
Operating conditions
Production load
Failure signatures
```

Output:

```text
failure_mode
risk_score
prediction_horizon
model_version
confidence
```

---

# 40. Root Cause Investigation

The system separates prediction from investigation.

Prediction:

```text
"There is a high probability of bearing degradation."
```

Investigation:

```text
"Why do we believe this?"
```

Investigation combines:

```text
Telemetry
+
Historical failures
+
Maintenance records
+
Production context
+
Quality context
+
Documents
```

---

# 41. Agentic Architecture

The agent layer is composed of specialized agents.

Recommended architecture:

```text
                       Orchestrator Agent
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
 Reliability Agent       OEE Agent          Quality Agent
          │                   │                   │
          └───────────────────┼───────────────────┘
                              │
                              ▼
                     Maintenance Agent
```

Not every workflow needs every agent.

The orchestrator decides which capability is required.

---

# 42. Orchestrator Agent

The orchestrator handles:

```text
intent classification
workflow routing
agent selection
context propagation
result aggregation
action routing
```

Example:

```text
User:
"Why did Line A's OEE drop?"

Orchestrator
    ↓
OEE Agent
    ↓
Reliability Agent
    ↓
Quality Agent
    ↓
Maintenance Agent
```

---

# 43. Reliability Agent

Responsibilities:

```text
Monitor reliability alerts
Investigate anomalies
Correlate telemetry
Inspect failure history
Inspect maintenance history
Search engineering knowledge
Generate hypotheses
Produce findings
Recommend maintenance
```

---

# 44. OEE Agent

Responsibilities:

```text
Calculate OEE
Explain OEE changes
Identify availability losses
Identify performance losses
Identify quality losses
Trace OEE losses to machines
```

---

# 45. Quality Agent

Responsibilities:

```text
Detect quality degradation
Correlate defects with machines
Correlate defects with process conditions
Identify candidate causes
Recommend investigation
```

---

# 46. Maintenance Agent

Responsibilities:

```text
Generate maintenance tasks
Create work orders
Assign work
Check technician requirements
Check spare parts
Track work order state
Verify maintenance outcomes
```

---

# 47. Agent Tools

Agents should never directly manipulate arbitrary database records.

They use typed tools.

Example:

```text
get_machine_health(machine_id)

get_recent_measurements(machine_id, window)

get_failure_history(machine_id)

get_maintenance_history(machine_id)

get_production_context(machine_id)

search_machine_manual(machine_id, query)

create_investigation(asset_id, alert_id)

create_work_order(asset_id, recommendation)

get_work_order_status(work_order_id)

verify_machine_recovery(machine_id)
```

---

# 48. Tool Architecture

```text
Agent
  ↓
Tool Selection
  ↓
Permission Check
  ↓
Input Validation
  ↓
Tool Execution
  ↓
Result Validation
  ↓
Agent Context
```

Tools are controlled boundaries.

---

# 49. Read Tools

Read-only tools include:

```text
get_machine
get_machine_health
get_sensor_measurements
get_failure_history
get_maintenance_history
get_production_context
get_oee
search_documents
```

These tools should have no side effects.

---

# 50. Action Tools

Action tools include:

```text
create_work_order
assign_work_order
schedule_maintenance
notify_engineer
escalate_alert
```

These tools require policy evaluation.

---

# 51. MCP Architecture

External systems can be connected through MCP where appropriate.

Example:

```text
                         Agent
                           │
                    ┌──────┴──────┐
                    ▼             ▼
                Snowflake        MCP
                                 │
                ┌────────────────┼──────────────┐
                ▼                ▼              ▼
              CMMS             Slack          Docs
```

MCP should be used where it provides a meaningful external capability.

It should not be introduced simply because it is available.

---

# 52. Work Order Integration

The preferred action flow is:

```text
Finding
   ↓
Recommendation
   ↓
Action Proposal
   ↓
Policy Check
   ↓
Human Approval if required
   ↓
CMMS / Work Management Tool
   ↓
Work Order Created
```

---

# 53. Command Center Architecture

The Streamlit application is the primary operational experience.

It should expose:

```text
Executive Overview
Reliability Overview
Asset Health
Alert Queue
Investigation Workspace
OEE Analytics
Maintenance
Work Orders
Agent Activity
Knowledge
System Health
```

---

# 54. Streamlit Architecture

```text
                 Streamlit
                    │
       ┌────────────┼────────────┐
       │            │            │
       ▼            ▼            ▼
    Analytics     Agents       Actions
       │            │            │
       └────────────┼────────────┘
                    ▼
                 Snowflake
```

Streamlit should not independently reproduce business logic that already exists in Snowflake or the agent layer.

It should primarily provide:

```text
presentation
interaction
workflow initiation
visualization
human approval
```

---

# 55. UI Design Philosophy

The command center should answer:

```text
WHAT IS WRONG?
WHY IS IT HAPPENING?
WHAT WILL HAPPEN NEXT?
WHAT SHOULD I DO?
```

---

# 56. Command Center Main Screen

Recommended layout:

```text
┌──────────────────────────────────────────────────────────────┐
│ FACTORY RELIABILITY COMMAND CENTER                           │
├──────────────┬──────────────┬──────────────┬────────────────┤
│ OEE          │ Availability │ Risk         │ Active Alerts  │
│ 84.7%        │ 91.2%        │ 7 High       │ 12             │
├──────────────┴──────────────┴──────────────┴────────────────┤
│                                                              │
│                 Factory Health Map                           │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│ Critical Reliability Alerts                                  │
│                                                              │
│ M204 | Bearing Risk | 87% | Investigate | Create WO         │
│ M118 | Temp Rise    | 74% | Investigate |                  │
│ M301 | OEE Drop     | ... | Investigate |                  │
├──────────────────────────────────────────────────────────────┤
│ OEE Trend                         │ Reliability Trend         │
│                                  │                           │
└──────────────────────────────────┴───────────────────────────┘
```

---

# 57. Asset Detail View

Selecting a machine should show:

```text
Machine Identity
Current Health
Failure Risk
Telemetry
Anomalies
Production Context
OEE Impact
Maintenance History
Failure History
Open Alerts
Open Work Orders
Relevant Documents
Agent Investigation
```

---

# 58. Investigation Workspace

The investigation screen should resemble an engineering investigation rather than a chatbot.

Example:

```text
M204 Reliability Investigation

Risk
87%

Likely Failure Mode
Bearing degradation

Evidence
────────────────────────────
✓ Vibration +48% above baseline
✓ Temperature trend increasing
✓ Similar historical failure
✓ Inspection overdue

Contradicting Evidence
────────────────────────────
• No abnormal motor current

Recommendation
────────────────────────────
Inspect bearing assembly within next
maintenance window.

Confidence
HIGH

[Create Work Order]
[Request Engineer Review]
[Dismiss]
```

---

# 59. Natural Language Interface

The system should also support questions such as:

```text
Why is M204 at risk?

Which machines are likely to fail
within the next 72 hours?

Why did OEE drop yesterday?

What caused Line A downtime?

Show me unresolved reliability alerts.

What maintenance should we schedule today?
```

Natural language is an interface to the ontology and agent layer.

It is not the primary source of truth.

---

# 60. Alert Lifecycle

```text
Telemetry
   ↓
Anomaly
   ↓
Risk Score
   ↓
Alert
   ↓
Prioritization
   ↓
Triage
   ↓
Investigation
   ↓
Recommendation
   ↓
Action
   ↓
Verification
   ↓
Resolution
```

---

# 61. Alert Prioritization

Priority should consider:

```text
Failure probability
Asset criticality
Production impact
OEE impact
Quality impact
Safety implications
Prediction horizon
Confidence
```

The resulting priority should be explainable.

---

# 62. Agent Investigation Workflow

The reliability investigation should follow:

```text
1. Receive alert

2. Resolve asset

3. Gather current machine health

4. Retrieve recent telemetry

5. Compare against baseline

6. Inspect anomalies

7. Retrieve failure history

8. Retrieve maintenance history

9. Retrieve production context

10. Retrieve quality context

11. Search engineering documents

12. Generate hypotheses

13. Evaluate evidence

14. Produce finding

15. Generate recommendation

16. Evaluate action policy

17. Request approval if needed

18. Create work order

19. Monitor outcome

20. Verify recovery
```

---

# 63. Example Agent Reasoning

Input:

```text
M204 failure risk = 87%
```

The agent should not immediately respond:

```text
"Replace the bearing."
```

Instead:

```text
M204
 ↓
Recent vibration
 ↓
Baseline deviation
 ↓
Temperature trend
 ↓
Historical failure
 ↓
Maintenance history
 ↓
Machine manual
 ↓
Evidence synthesis
 ↓
Hypothesis
 ↓
Finding
 ↓
Recommendation
```

---

# 64. Action Policy Engine

Every action passes through policy.

```text
Agent
 ↓
Action Proposal
 ↓
Policy Engine
 ↓
Allowed?
 ├── No → Reject
 │
 ├── Approval Required → Human
 │
 └── Yes → Execute
```

---

# 65. Policy Example

```text
IF
action = CREATE_WORK_ORDER

AND
asset_criticality = CRITICAL

THEN
human_approval = REQUIRED
```

Another:

```text
IF
action = NOTIFY_ENGINEER

AND
severity >= HIGH

THEN
auto_execute = TRUE
```

---

# 66. Human-in-the-Loop

Humans should be involved at points where judgment or accountability matters.

Examples:

```text
Approve work order
Approve high-risk recommendation
Override agent recommendation
Confirm failure
Close investigation
```

The UI should make these decisions explicit.

---

# 67. Agent Failure Handling

Agents must fail safely.

Possible failures:

```text
Missing telemetry
Unavailable CMMS
Conflicting evidence
Low confidence
Tool timeout
Invalid tool arguments
Missing machine documentation
Unknown asset
```

The agent should respond with:

```text
KNOWN
UNKNOWN
INSUFFICIENT_EVIDENCE
ACTION_BLOCKED
```

rather than hallucinating.

---

# 68. Data Quality Guardrails

Before intelligence processing:

```text
Schema validation
Null validation
Range validation
Timestamp validation
Duplicate detection
Referential integrity
Sensor health checks
```

---

# 69. Agent Guardrails

Before generating an operational recommendation:

```text
Asset exists
+
Evidence exists
+
Data is recent enough
+
Confidence threshold satisfied
+
No conflicting critical evidence
+
Policy allows action
```

---

# 70. Action Guardrails

Before executing an action:

```text
Validate arguments
 ↓
Validate identity
 ↓
Validate authorization
 ↓
Validate policy
 ↓
Require approval if needed
 ↓
Execute
 ↓
Record audit event
```

---

# 71. Audit Architecture

Every important action should produce:

```text
timestamp
actor
agent
tool
input
output
resource
decision
policy
approval
result
```

Example:

```text
Agent:
ReliabilityAgent

Decision:
Create Work Order

Asset:
M204

Evidence:
E1, E2, E3, E4

Policy:
Critical asset → approval required

Approver:
Reliability Engineer

Result:
WO-98421 created
```

---

# 72. Observability

The platform should monitor:

## Data

```text
pipeline latency
row counts
freshness
quality failures
```

## ML

```text
prediction distribution
false positives
false negatives
model drift
```

## Agents

```text
execution count
latency
tool calls
failure rate
confidence
```

## Actions

```text
work order creation
approval rate
action failures
verification success
```

---

# 73. Model Lifecycle

ML models should have:

```text
model_id
model_version
training_data_version
features
metrics
training_timestamp
deployment_status
```

Predictions should retain model version.

This makes historical decisions reproducible.

---

# 74. ML Feedback Loop

Once maintenance is completed:

```text
Work Order
   ↓
Maintenance Event
   ↓
Verification
   ↓
Actual Outcome
   ↓
Prediction Evaluation
   ↓
Model Metrics
   ↓
Future Model Improvement
```

---

# 75. Reliability Learning Loop

The complete learning loop is:

```text
                    ┌───────────────┐
                    │   Telemetry   │
                    └───────┬───────┘
                            ↓
                    ┌───────────────┐
                    │   Prediction  │
                    └───────┬───────┘
                            ↓
                    ┌───────────────┐
                    │ Investigation │
                    └───────┬───────┘
                            ↓
                    ┌───────────────┐
                    │    Action     │
                    └───────┬───────┘
                            ↓
                    ┌───────────────┐
                    │    Outcome    │
                    └───────┬───────┘
                            ↓
                    ┌───────────────┐
                    │   Learning    │
                    └───────┬───────┘
                            │
                            └────────→ Telemetry
```

---

# 76. Security Architecture

Security should be implemented at the platform level.

Key requirements:

```text
Authentication
Authorization
Role-based access
Least privilege
Data masking where required
Audit logging
Tool permissions
Agent permissions
Environment separation
```

---

# 77. Environment Architecture

Use separate environments:

```text
DEV
 ↓
TEST
 ↓
STAGING
 ↓
PRODUCTION
```

For the initial build:

```text
DEV
TEST
DEMO
```

may be sufficient.

---

# 78. Repository Architecture

Recommended repository:

```text
factory-reliability-command-center/
│
├── README.md
├── architecture.md
├── ontology.md
│
├── docs/
│   ├── architecture/
│   ├── agents/
│   ├── data/
│   ├── integrations/
│   └── runbooks/
│
├── snowflake/
│   ├── databases/
│   ├── schemas/
│   ├── tables/
│   ├── views/
│   ├── dynamic_tables/
│   ├── streams/
│   ├── tasks/
│   ├── procedures/
│   └── semantic/
│
├── data/
│   ├── synthetic/
│   ├── scenarios/
│   └── reference/
│
├── agents/
│   ├── orchestrator/
│   ├── reliability/
│   ├── oee/
│   ├── quality/
│   └── maintenance/
│
├── tools/
│   ├── read/
│   ├── analysis/
│   └── actions/
│
├── app/
│   └── streamlit/
│
├── tests/
│   ├── data/
│   ├── sql/
│   ├── semantic/
│   ├── agents/
│   └── integration/
│
├── scripts/
│
└── .coco/
    └── skills/
```

---

# 79. Why This Repository Structure

The repository separates:

```text
Data
Agents
Tools
Application
Tests
Architecture
```

This prevents the Streamlit application from becoming the place where all business logic accidentally lives.

---

# 80. Software Responsibilities

The Software Engineer primarily owns:

```text
Agent orchestration
Agent tools
Application
Streamlit UI
MCP integrations
Action layer
APIs
Authentication
Application testing
Agent evaluation
```

The Data Engineer primarily owns:

```text
Snowflake architecture
Data ingestion
Data models
Transformation
Telemetry pipelines
Feature engineering
OEE calculations
Semantic layer
Data quality
ML data preparation
```

Both engineers jointly own:

```text
Ontology
Agent workflow
Integration contracts
Testing
Demo scenarios
Architecture decisions
```

---

# 81. Data Engineer Architecture Ownership

The Data Engineer owns:

```text
Source → Snowflake
```

including:

```text
Raw ingestion
Data normalization
Asset model
Telemetry model
Production model
Maintenance model
Quality model
OEE model
Feature pipelines
Semantic model
Data quality
```

---

# 82. Software Engineer Architecture Ownership

The Software Engineer owns:

```text
Snowflake intelligence → User / Action
```

including:

```text
Agent orchestration
Tools
Workflows
Streamlit
MCP
Action APIs
Approval workflows
Application state
```

---

# 83. Shared Boundary

The shared contract is:

```text
Ontology
+
Semantic Layer
+
Tool Contracts
```

The Data Engineer produces trusted data concepts.

The Software Engineer consumes those concepts through semantic interfaces and tools.

---

# 84. Streamlit and Stitch

Stitch can be used as the design/reference surface for the UI.

The recommended workflow is:

```text
Stitch
 ↓
Visual design
 ↓
Component specification
 ↓
Streamlit implementation
 ↓
Snowflake integration
 ↓
Agent integration
```

Streamlit should reproduce the **experience and information architecture**, not necessarily the exact underlying frontend implementation.

---

# 85. UI Technology Boundary

Recommended:

```text
Stitch
    ↓
Design inspiration / prototype

Streamlit
    ↓
Actual product UI

Snowflake
    ↓
Data + intelligence

Agent Layer
    ↓
Investigation + actions
```

Do not create two separate production UIs.

---

# 86. End-to-End Runtime Flow

A normal reliability event should flow as follows:

```text
1. Sensor emits measurement

2. Measurement enters Snowflake

3. Pipeline processes measurement

4. Features are calculated

5. Baseline is evaluated

6. Anomaly is detected

7. Failure risk is calculated

8. Alert is generated

9. Alert appears in Command Center

10. Reliability Agent starts investigation

11. Agent retrieves telemetry

12. Agent retrieves maintenance history

13. Agent retrieves failure history

14. Agent retrieves production context

15. Agent searches documentation

16. Agent constructs evidence graph

17. Agent evaluates hypotheses

18. Agent produces finding

19. Agent generates recommendation

20. Policy engine evaluates action

21. Human approval occurs if required

22. Work order is created

23. Technician performs maintenance

24. Maintenance result is recorded

25. System verifies machine recovery

26. OEE impact is recalculated

27. Outcome is stored

28. Result feeds future model evaluation
```

---

# 87. Complete Architecture Diagram

```text
                         FACTORY
                            │
          ┌─────────────────┼──────────────────┐
          │                 │                  │
          ▼                 ▼                  ▼
       Sensors            PLC/SCADA          MES
          │                 │                  │
          └─────────────────┼──────────────────┘
                            ▼
                     DATA INGESTION
                            │
          ┌─────────────────┼──────────────────┐
          │                 │                  │
          ▼                 ▼                  ▼
        OT Data           ERP/CMMS          Documents
          │                 │                  │
          └─────────────────┼──────────────────┘
                            ▼
                  ┌────────────────────┐
                  │      SNOWFLAKE     │
                  │                    │
                  │       RAW          │
                  │        ↓           │
                  │   STANDARDIZED     │
                  │        ↓           │
                  │     CURATED        │
                  │        ↓           │
                  │      FEATURES      │
                  │        ↓           │
                  │     SEMANTIC       │
                  │        ↓           │
                  │   INTELLIGENCE     │
                  └─────────┬──────────┘
                            │
             ┌──────────────┼───────────────┐
             │              │               │
             ▼              ▼               ▼
          Analytics          ML          Knowledge
             │              │               │
             └──────────────┼───────────────┘
                            ▼
                    SEMANTIC LAYER
                            │
                            ▼
                  ┌────────────────────┐
                  │    AGENTIC LAYER   │
                  │                    │
                  │   Orchestrator     │
                  │        │           │
                  │   ┌────┼────┐      │
                  │   ▼    ▼    ▼      │
                  │ Rel   OEE Quality   │
                  │       │             │
                  │ Maintenance        │
                  └─────────┬──────────┘
                            │
                    ┌───────┴────────┐
                    │                │
                    ▼                ▼
                 READ TOOLS       ACTION TOOLS
                    │                │
                    │                ▼
                    │          Policy Engine
                    │                │
                    │        ┌───────┴────────┐
                    │        │                │
                    │        ▼                ▼
                    │     Approval         Execute
                    │        │                │
                    │        └───────┬────────┘
                    │                ▼
                    │         CMMS / ERP / Slack
                    │
                    └──────────┬─────────────
                               ▼
                       STREAMLIT COMMAND
                           CENTER
                               │
             ┌─────────────────┼─────────────────┐
             │                 │                 │
             ▼                 ▼                 ▼
          Dashboard       Investigation       Actions
             │                 │                 │
             └─────────────────┼─────────────────┘
                               ▼
                          HUMAN USER
                               │
                               ▼
                         MAINTENANCE
                               │
                               ▼
                          VERIFICATION
                               │
                               ▼
                         MACHINE HEALTH
                               │
                               ▼
                              OEE
                               │
                               └──────→ FEEDBACK
```

---

# 88. Critical Architecture Decision: Snowflake-Centric

The system should avoid this anti-pattern:

```text
                Python Backend
                 /          \
                /            \
       PostgreSQL             Snowflake
          │                       │
          └────────────┬──────────┘
                       │
                   Streamlit
```

This creates two sources of truth.

Instead:

```text
                    SNOWFLAKE
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
       Agents       Streamlit      Analytics
```

Snowflake should remain the system of record.

---

# 89. Critical Architecture Decision: Agents Are Not the Database

Agents should not own business state.

Bad:

```text
Agent memory
   ↓
Machine state
```

Preferred:

```text
Snowflake
   ↓
Canonical state
   ↓
Agent context
```

Agent memory may contain conversational context, but authoritative operational state belongs in governed data stores.

---

# 90. Critical Architecture Decision: Agents Are Not Deterministic Pipelines

Do not use an LLM for:

```text
simple aggregation
simple filtering
OEE arithmetic
basic thresholds
deterministic transformations
```

Use SQL / deterministic computation.

Use agents for:

```text
investigation
reasoning
context synthesis
document interpretation
hypothesis generation
recommendation
workflow orchestration
```

This distinction improves reliability and cost.

---

# 91. Critical Architecture Decision: Prediction ≠ Diagnosis

The ML model predicts:

```text
High probability of bearing degradation.
```

The agent investigates:

```text
Why?
```

The maintenance workflow decides:

```text
What should happen?
```

The technician verifies:

```text
Was the diagnosis correct?
```

These should remain separate architectural responsibilities.

---

# 92. Critical Architecture Decision: Recommendation ≠ Action

The system must distinguish:

```text
Recommendation:
Inspect bearing.

Action:
Create work order.

Execution:
WO-98421 created.

Outcome:
Bearing replaced.

Verification:
Vibration returned to baseline.
```

This distinction makes the system auditable.

---

# 93. Testing Architecture

Testing occurs at five levels.

```text
Data
 ↓
SQL
 ↓
Semantic
 ↓
Agent
 ↓
End-to-End
```

---

# 94. Data Tests

Validate:

```text
referential integrity
null constraints
duplicates
timestamps
ranges
freshness
```

---

# 95. SQL Tests

Validate:

```text
feature calculations
OEE calculations
risk aggregation
downtime calculations
joins
incremental processing
```

---

# 96. Semantic Tests

Ask natural-language questions.

Example:

```text
Which machine has the highest failure risk?
```

Verify:

```text
correct entity
correct metric
correct time window
correct machine
```

---

# 97. Agent Tests

Test scenarios such as:

### Scenario A

```text
Strong telemetry evidence
+
historical failure
+
maintenance overdue
```

Expected:

```text
High-confidence investigation.
```

### Scenario B

```text
High anomaly score
+
no historical evidence
+
missing maintenance data
```

Expected:

```text
Lower confidence.
No fabricated diagnosis.
```

### Scenario C

```text
Tool unavailable
```

Expected:

```text
Graceful fallback.
```

---

# 98. Action Tests

Test:

```text
Unauthorized action
Approval-required action
Invalid asset
Duplicate work order
CMMS unavailable
Action timeout
```

---

# 99. End-to-End Test

A complete synthetic failure scenario should execute:

```text
Sensor anomaly
→ Failure risk
→ Alert
→ Investigation
→ Evidence
→ Finding
→ Recommendation
→ Approval
→ Work order
→ Maintenance
→ Recovery
→ Verification
→ OEE update
```

This is the most important product test.

---

# 100. Demo Scenario

The primary demonstration should revolve around one machine.

Example:

```text
Machine M204
```

The story:

```text
M204 is operating normally.

↓

Vibration begins increasing.

↓

System detects anomaly.

↓

Failure risk rises to 87%.

↓

Alert appears.

↓

Reliability Agent investigates.

↓

Agent correlates:
    telemetry
    maintenance history
    failure history
    manual

↓

Agent concludes:
bearing degradation is the leading hypothesis.

↓

Agent creates recommendation.

↓

Human approves work order.

↓

Work order is created.

↓

Technician performs inspection.

↓

Bearing is replaced.

↓

Machine restarts.

↓

Vibration returns to baseline.

↓

OEE recovers.

↓

System records outcome.
```

This demonstrates the entire architecture in one coherent story.

---

# 101. Secondary OEE Scenario

The second demonstration should show:

```text
OEE:
91% → 82%
```

The OEE Agent investigates.

```text
OEE
 ↓
Availability loss
 ↓
Machine M204
 ↓
Bearing issue
 ↓
Downtime
```

The system explains the OEE decline in causal terms rather than merely displaying a graph.

---

# 102. Secondary Quality Scenario

Example:

```text
Defect rate:
1.2% → 4.7%
```

The Quality Agent investigates:

```text
Defect
 ↓
Production Run
 ↓
Machine
 ↓
Process conditions
 ↓
Telemetry
 ↓
Maintenance
```

The system identifies candidate contributing conditions and presents evidence.

---

# 103. Command Center KPIs

The primary dashboard should expose:

```text
OEE
Availability
Performance
Quality
Active Alerts
Critical Assets
High Failure Risks
Predicted Failures
Unplanned Downtime
Open Work Orders
Maintenance Completion
Recovery Rate
```

---

# 104. Reliability KPIs

Track:

```text
Failure prediction accuracy
False positive rate
False negative rate
Mean time to detection
Mean time to intervention
Mean time to repair
Repeat failure rate
```

---

# 105. Agent KPIs

Track:

```text
Investigation completion rate
Recommendation acceptance rate
Human override rate
Tool failure rate
Average investigation duration
Evidence count
Confidence distribution
```

---

# 106. Business Value Metrics

The system should ultimately measure:

```text
Downtime avoided
Maintenance cost avoided
Production recovered
OEE improvement
Failure detection lead time
Maintenance efficiency
```

These should be calculated from actual events rather than invented headline numbers.

---

# 107. Architecture for Production Evolution

The initial prototype can use:

```text
Synthetic data
Snowflake
Streamlit
CoCo
Simulated CMMS
```

The architecture should allow later replacement with:

```text
Real OT ingestion
Real ERP
Real CMMS
Real MES
Enterprise authentication
Production scheduling
Production-grade observability
```

without redesigning the ontology.

---

# 108. Production Deployment Evolution

### Phase 1

```text
Synthetic Factory
Snowflake
CoCo
Streamlit
Agentic Investigation
```

### Phase 2

```text
Near-real-time telemetry
External CMMS
External notifications
```

### Phase 3

```text
Multiple plants
Multiple asset classes
Advanced ML
Production integrations
```

### Phase 4

```text
Enterprise reliability platform
```

---

# 109. Scalability

The architecture should scale across:

```text
1 machine
→ 100 machines
→ 10,000 machines
→ multiple plants
→ multiple organizations
```

The key scaling mechanisms are:

```text
Snowflake compute
incremental processing
partition-aware data design
semantic abstraction
stateless agent execution
tool-based actions
```

---

# 110. Multi-Tenant Evolution

For an enterprise SaaS version:

```text
Organization
 ↓
Site
 ↓
Plant
```

becomes the security boundary.

All entities should retain:

```text
organization_id
site_id
plant_id
```

where appropriate.

---

# 111. Cost Architecture

The system should avoid unnecessary LLM calls.

Use:

```text
SQL
```

for deterministic computation.

Use:

```text
ML
```

for numerical prediction.

Use:

```text
Agents
```

for reasoning and orchestration.

This creates:

```text
SQL → cheapest deterministic layer

ML → specialized prediction layer

Agent → expensive reasoning layer
```

Agents should be triggered when their reasoning adds value.

---

# 112. Latency Architecture

Not all workflows require real-time responses.

### Near-real-time

```text
Telemetry ingestion
Anomaly detection
Risk scoring
Alert generation
```

### Interactive

```text
Investigation
Natural language questions
Dashboard interaction
```

### Asynchronous

```text
Document processing
Large investigations
Model training
Historical analysis
```

---

# 113. Event Correlation

Correlation IDs connect the system.

Example:

```text
correlation_id = REL-2026-00042
```

This ID links:

```text
Anomaly
Alert
Investigation
AgentExecution
Recommendation
Action
WorkOrder
MaintenanceEvent
Verification
```

This enables end-to-end tracing.

---

# 114. System State vs Event History

The system should maintain both:

```text
Current state
```

and:

```text
Historical events
```

Example:

```text
Machine.status = RUNNING
```

does not replace:

```text
MachineStopped
MachineFaulted
MaintenanceStarted
MachineStarted
```

events.

Both are required.

---

# 115. Architecture Contracts

Every major layer should expose explicit contracts.

## Data Contract

Defines:

```text
schema
types
keys
freshness
quality
```

## Semantic Contract

Defines:

```text
entities
relationships
metrics
verified queries
```

## Agent Contract

Defines:

```text
input
context
tools
output
confidence
```

## Tool Contract

Defines:

```text
name
arguments
permissions
side effects
result
errors
```

## Action Contract

Defines:

```text
authorization
approval
execution
audit
verification
```

---

# 116. Reliability Agent Contract

Input:

```text
alert_id
asset_id
investigation_context
```

Output:

```text
investigation_id
finding
evidence[]
confidence
recommendation
recommended_action
```

The output should be structured rather than free-form text only.

---

# 117. Tool Contract Example

Conceptually:

```text
Tool:
create_work_order

Input:
{
    asset_id,
    recommendation_id,
    priority,
    description
}

Output:
{
    work_order_id,
    status,
    external_reference
}
```

The exact implementation may differ, but the contract must remain deterministic.

---

# 118. Agent Output Contract

An investigation should produce:

```text
{
    "investigation_id": "...",
    "asset_id": "...",
    "finding": "...",
    "failure_mode": "...",
    "evidence": [],
    "confidence": 0.87,
    "recommendation": "...",
    "action_required": true
}
```

The natural-language explanation is generated from this structured state.

---

# 119. Explainability

Every major conclusion should be explainable.

For example:

```text
Why is M204 high risk?
```

The system should return:

```text
1. Vibration is 48% above baseline.
2. Temperature has increased continuously.
3. Similar behavior preceded two historical bearing failures.
4. Bearing inspection is overdue.
5. Current operating load is elevated.
```

Each item should be traceable to source data.

---

# 120. Evidence Citation

The command center should allow users to drill into evidence.

Example:

```text
Evidence #1
Source:
Telemetry

Timestamp:
10:14:32

Signal:
Vibration RMS

Observed:
0.82 g

Baseline:
0.55 g
```

Another:

```text
Evidence #2
Source:
Maintenance

Last bearing inspection:
147 days ago
```

---

# 121. Agent Transparency

The UI should expose:

```text
Agent
Tools used
Evidence consulted
Finding
Confidence
Recommendation
Action
```

Avoid exposing private chain-of-thought.

Instead expose concise, auditable reasoning artifacts:

```text
Evidence
Decision factors
Conclusion
```

---

# 122. Graceful Fallback Architecture

If AI is unavailable:

```text
Dashboard
 ↓
Deterministic analytics
 ↓
Alerting
```

The system should remain operational.

If a document search fails:

```text
Agent
 ↓
Structured data investigation
 ↓
Lower confidence
```

If CMMS fails:

```text
Recommendation
 ↓
Action pending
 ↓
Retry / human workflow
```

---

# 123. Disaster and Recovery

Critical state should be persisted in Snowflake.

Agents should be restartable.

Actions should be idempotent where possible.

For example:

```text
create_work_order
```

should avoid creating duplicate work orders when retried.

Use:

```text
idempotency_key
```

where appropriate.

---

# 124. Idempotency

Example:

```text
idempotency_key =
asset_id + recommendation_id
```

If the same action is retried:

```text
Existing work order
        ↓
Return existing reference
```

rather than:

```text
Create duplicate work order
```

---

# 125. Data Retention

Retention policies should differ by data type.

Potential categories:

```text
Raw telemetry
Curated telemetry
Events
Maintenance history
Agent executions
Audit events
Documents
```

Exact retention should be configurable by deployment.

---

# 126. Architecture Decision Summary

The system makes these foundational decisions:

| Decision                 | Choice                                 |
| ------------------------ | -------------------------------------- |
| System of record         | Snowflake                              |
| Canonical business model | Industrial ontology                    |
| Analytical interface     | Semantic layer                         |
| AI development surface   | CoCo                                   |
| Agent architecture       | Specialized agents + orchestrator      |
| UI                       | Streamlit                              |
| UI design                | Stitch-assisted                        |
| Pipeline                 | Snowflake-native                       |
| ML                       | Snowflake-native where practical       |
| External actions         | Tools / MCP / APIs                     |
| Maintenance action       | Work order                             |
| Human control            | Policy + approval                      |
| Audit                    | Snowflake                              |
| Knowledge                | Snowflake-backed document/search layer |
| Source control           | Git                                    |
| Testing                  | Data + SQL + semantic + agent + E2E    |

---

# 127. What CoCo Owns vs What the Product Owns

This distinction is important.

CoCo is the:

```text
AI-native development / operational interface
```

The product is:

```text
Snowflake
+
Data Pipelines
+
Ontology
+
Semantic Layer
+
ML
+
Agents
+
Tools
+
Streamlit
+
Integrations
```

CoCo helps the team build, inspect, execute, validate, and operate this system.

The product itself should not become dependent on a developer manually asking CoCo questions for every runtime operation.

---

# 128. Complete System Responsibility Model

```text
                    CoCo
                     │
          ┌──────────┼───────────┐
          ▼          ▼           ▼
       Build       Run        Validate
          │          │           │
          └──────────┼───────────┘
                     ▼
                  Product
                     │
     ┌───────────────┼────────────────┐
     ▼               ▼                ▼
 Snowflake         Agents          Streamlit
     │               │                │
     │               ▼                │
     │             Tools              │
     │               │                │
     │               ▼                │
     │           Work Orders          │
     │                                │
     └────────────────────────────────┘
```

---

# 129. The Product's Core Loop

Everything ultimately reduces to:

```text
OBSERVE
   ↓
UNDERSTAND
   ↓
PREDICT
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

Mapped to the system:

```text
OBSERVE
→ Telemetry

UNDERSTAND
→ Analytics + Semantic Layer

PREDICT
→ ML

INVESTIGATE
→ Agents

DECIDE
→ Evidence + Recommendation

ACT
→ Tools + Work Orders

VERIFY
→ Outcome + Health

LEARN
→ Historical data + Model evaluation
```

---

# 130. Final Architecture

The Factory Reliability Command Center is ultimately:

```text
                       ┌───────────────────────┐
                       │       HUMAN           │
                       │ Reliability Engineer  │
                       │ Plant Manager         │
                       │ Maintenance Engineer  │
                       └───────────┬───────────┘
                                   │
                                   ▼
                       ┌───────────────────────┐
                       │     STREAMLIT         │
                       │   COMMAND CENTER      │
                       └───────────┬───────────┘
                                   │
                                   ▼
                       ┌───────────────────────┐
                       │    AGENTIC LAYER      │
                       │                       │
                       │ Orchestrator          │
                       │ Reliability           │
                       │ OEE                   │
                       │ Quality               │
                       │ Maintenance           │
                       └───────────┬───────────┘
                                   │
                         ┌─────────┴─────────┐
                         ▼                   ▼
                  Semantic Layer         Tool Layer
                         │                   │
                         └─────────┬─────────┘
                                   ▼
                       ┌───────────────────────┐
                       │       SNOWFLAKE       │
                       │                       │
                       │ Ontology              │
                       │ Telemetry             │
                       │ Production            │
                       │ Quality               │
                       │ Maintenance           │
                       │ Reliability           │
                       │ Knowledge             │
                       │ OEE                   │
                       │ Agent State           │
                       │ Audit                 │
                       └───────────┬───────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
                 Factory          ERP            CMMS
                 / OT             / MES          / EAM
                    │              │              │
                    └──────────────┼──────────────┘
                                   ▼
                             REAL WORLD
                                   │
                                   ▼
                              MAINTENANCE
                                   │
                                   ▼
                              MACHINE
                                   │
                                   ▼
                              NEW DATA
                                   │
                                   └──────────────→ LOOP
```

The architecture therefore creates a **closed-loop industrial intelligence system**:

> **Snowflake provides the governed industrial context.
> The semantic layer gives that context meaning.
> ML detects and predicts.
> Agents investigate and reason.
> Tools turn decisions into actions.
> Streamlit gives humans command and control.
> Maintenance creates real-world outcomes.
> Those outcomes return to Snowflake and improve the system.**

That is the architecture to build against.
