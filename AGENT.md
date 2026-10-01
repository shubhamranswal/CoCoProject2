# CoCo Factory Intelligence Platform

## Agent Build Specification for Antigravity

> **Purpose:** This file is the authoritative implementation brief for
> building CoCo, a production-oriented factory reliability and
> operations intelligence product on Snowflake.
>
> **Primary implementation environment:** Snowflake + Streamlit.
>
> **Important:** Build the system so the synthetic dataset can be
> replaced by live factory systems later without redesigning the core
> product.

------------------------------------------------------------------------

# 1. Product Definition

## 1.1 Product name

**CoCo**: a Snowflake-native factory intelligence and reliability agent.

## 1.2 Product mission

CoCo helps factory teams understand machine health, investigate abnormal
conditions, predict degradation-type failures, connect those predictions
to maintenance history and operational context, and coordinate
maintenance actions.

The product combines:

-   Industrial sensor telemetry
-   Machine/component hierarchy
-   Production and downtime data
-   Maintenance work orders
-   Technician notes
-   Manuals and SOPs
-   Spare-part inventory
-   Suppliers and purchase orders
-   Alerts
-   ML failure predictions
-   Agentic investigation and controlled actions

## 1.3 Core product principle

**Snowflake knows the factory.\
The ML model predicts what may happen.\
Cortex Search retrieves what people and manuals know.\
CoCo connects those facts, explains the situation, and coordinates the
next action.**

Do not use the LLM to replace the predictive model.

------------------------------------------------------------------------

# 2. Current Dataset

The current synthetic dataset is suitable for building the complete
product architecture.

It is based on real-world-style factory values but is synthetic.

## 2.1 Current/final dataset size

There are **19 tables/files**:

### OT

1.  `sensor`
2.  `sensor_reading.csv.gz`
3.  `sensor_reading_hourly.csv.gz`

### Plant and maintenance

4.  `machine`
5.  `component`
6.  `production_run`
7.  `downtime_event`
8.  `maintenance_work_order`
9.  `technician`

### ERP

10. `product`
11. `production_order`
12. `spare_part`
13. `supplier`
14. `purchase_order`
15. `wo_part_usage`

### Text / knowledge

16. `maintenance_log`
17. `knowledge_doc`

### Alerts / ML

18. `alert`
19. `prediction`

The original dataset description said 18 tables, but the complete
dataset contains 19 because `technician` is also a table.

## 2.2 Dataset characteristics

-   25 machines
-   144 sensors
-   141 components
-   12 months of factory history
-   Date range approximately 1 Oct 2025 to 28 Sep 2026
-   2,903,040 minute-resolution sensor rows
-   1,254,528 hourly sensor rows
-   19,593 production runs
-   67,385 downtime events
-   637 work orders
-   610 maintenance logs
-   16 knowledge documents
-   1,142 alerts
-   326 predictions
-   32 spare parts
-   217 purchase orders
-   12 suppliers
-   6 technicians

## 2.3 Synthetic-data limitation

The data is appropriate for:

-   Product development
-   Architecture validation
-   Agent workflow validation
-   Snowflake implementation
-   UI development
-   ML pipeline demonstration
-   End-to-end demonstrations

It is **not** evidence of real-world model performance.

The degradation patterns were intentionally built into the synthetic
generator, so reported model metrics can be optimistic. Any
submission/demo must clearly describe the model metrics as
synthetic-data validation.

The real-world validation plan should include public datasets such as
CWRU or NASA bearing datasets and, eventually, actual factory signals.

------------------------------------------------------------------------

# 3. Current Important Scenarios

The dataset contains live/degrading scenarios at the end of the
synthetic window:

-   M21: bearing degradation
-   M15: motor degradation
-   M05: coolant degradation

The current prediction data identifies all three as high-risk with the
intended component.

These should be the canonical product demonstrations.

Example:

> Why is M21 at risk, what happened last time, what does the maintenance
> SOP recommend, is the required bearing available, and which production
> order could be affected?

CoCo should answer this by combining structured Snowflake data, Cortex
Search, prediction output, inventory, and production context.

------------------------------------------------------------------------

# 4. Product Architecture

## 4.1 High-level architecture

``` text
                         USER
                           |
                           v
                     STREAMLIT UI
                           |
                           v
                     COCO AGENT
                           |
              +------------+------------+
              |            |            |
              v            v            v
        Structured      Knowledge      Actions
         Analytics       Search
              |            |            |
              +------------+------------+
                           |
                           v
                       SNOWFLAKE
                           |
        +------------------+------------------+
        |                  |                  |
        v                  v                  v
   Factory Data           ML              Knowledge
        |                  |                  |
   OT / MES / ERP      Features         Manuals / SOPs
   Maintenance         Model            Technician notes
   Production          Prediction
   Inventory           Risk
```

## 4.2 Product boundaries

### Streamlit

User-facing application.

### CoCo / Cortex Agent

Reasoning, orchestration, tool selection, explanation, and controlled
actions.

### Snowflake

System of record and analytical/AI platform.

### ML model

Failure prediction.

### Cortex Search

Retrieval over maintenance notes and knowledge documents.

Do not collapse these responsibilities into one LLM.

------------------------------------------------------------------------

# 5. LLM / Agent Decision

## 5.1 No separate custom LLM is required for the initial product

Do not create or train a separate LLM.

Use Snowflake Cortex capabilities for the agent/reasoning layer.

CoCo should be implemented as the configured factory agent that
orchestrates:

-   Structured data access
-   Cortex Analyst/semantic structured-data capabilities as appropriate
-   Cortex Search
-   Prediction tables
-   Alert tables
-   Approved SQL/procedure/action tools

Snowflake's current product direction should be checked against the
latest documentation when implementing syntax and APIs.

## 5.2 LLM responsibility

The LLM/agent is responsible for:

-   Understanding the user's question
-   Selecting appropriate tools
-   Combining evidence
-   Explaining findings
-   Retrieving relevant maintenance history
-   Retrieving manuals/SOPs
-   Connecting predictions to operational context
-   Proposing actions
-   Executing only approved/safe actions

## 5.3 ML responsibility

The ML model is responsible for:

-   Failure probability
-   Risk classification
-   Suspected component
-   Model features
-   Model scoring

Never ask the LLM to infer failure probability from text.

------------------------------------------------------------------------

# 6. Streamlit Interaction Model

The final interaction should be:

``` text
User
 |
 | "Why is M21 at risk?"
 v
Streamlit
 |
 v
CoCo Agent
 |
 +--> structured Snowflake queries
 |
 +--> Cortex Search
 |
 +--> prediction / alert / inventory / production data
 |
 v
Evidence-backed response
 |
 v
Recommended action
 |
 v
Human approval if operational action is requested
```

The user should not need to know table names or SQL.

------------------------------------------------------------------------

# 7. Snowflake Database Architecture

Create:

``` text
COCO_FACTORY
|
+-- RAW
+-- CORE
+-- ANALYTICS
+-- ML
+-- KNOWLEDGE
+-- APP
```

## 7.1 RAW

Contains ingested source data with minimal transformation.

Tables:

-   RAW.MACHINE
-   RAW.COMPONENT
-   RAW.SENSOR
-   RAW.SENSOR_READING
-   RAW.SENSOR_READING_HOURLY
-   RAW.PRODUCTION_RUN
-   RAW.PRODUCTION_ORDER
-   RAW.DOWNTIME_EVENT
-   RAW.MAINTENANCE_WORK_ORDER
-   RAW.MAINTENANCE_LOG
-   RAW.TECHNICIAN
-   RAW.PRODUCT
-   RAW.SPARE_PART
-   RAW.SUPPLIER
-   RAW.PURCHASE_ORDER
-   RAW.WO_PART_USAGE
-   RAW.KNOWLEDGE_DOC
-   RAW.ALERT
-   RAW.PREDICTION

Add ingestion metadata where appropriate:

-   `_SOURCE_FILE`
-   `_LOADED_AT`
-   `_BATCH_ID`
-   `_INGESTION_TS`
-   `_SOURCE_EVENT_ID`

## 7.2 CORE

Clean, conformed relational factory model.

Use stable IDs and explicit relationships.

Key relationships:

``` text
Machine
  -> Component
      -> Sensor

Machine
  -> Production Run
      -> Production Order

Machine
  -> Downtime Event
      -> Work Order

Work Order
  -> Maintenance Log
  -> Part Usage
      -> Spare Part
          -> Supplier

Machine
  -> Prediction
  -> Alert
```

## 7.3 ANALYTICS

Build reusable analytical views/dynamic tables such as:

-   MACHINE_HEALTH_DAILY
-   MACHINE_OEE_DAILY
-   MACHINE_DOWNTIME_DAILY
-   MAINTENANCE_HISTORY
-   PRODUCTION_RISK
-   INVENTORY_RISK
-   MACHINE_RISK
-   ALERT_SUMMARY
-   WORK_ORDER_SUMMARY

Use Dynamic Tables where declarative refresh is appropriate.

Use Streams + Tasks where event/action behavior is required.

------------------------------------------------------------------------

# 8. Data Loading

## 8.1 Initial bulk load

Use:

``` text
Local files
   |
   v
Snowflake internal stage
   |
   v
RAW tables
   |
   v
validation
   |
   v
CORE
```

Support `.csv` and `.csv.gz`.

Do not bypass RAW during initial implementation.

## 8.2 Loading order

Recommended:

1.  machine
2.  component
3.  sensor
4.  technician
5.  product
6.  supplier
7.  spare_part
8.  production_order
9.  production_run
10. downtime_event
11. maintenance_work_order
12. maintenance_log
13. purchase_order
14. wo_part_usage
15. knowledge_doc
16. alert
17. prediction
18. sensor_reading
19. sensor_reading_hourly

Foreign-key validation must be performed after loading.

------------------------------------------------------------------------

# 9. Data Quality Requirements

Build SQL checks for:

-   Primary-key uniqueness
-   Null critical IDs
-   Foreign-key integrity
-   Duplicate sensor/timestamp rows
-   Timestamp ordering
-   Sensor coverage
-   Machine coverage
-   Missing telemetry windows
-   Unexpected sensor values
-   Threshold consistency
-   Production-order/run consistency
-   Work-order timestamp consistency
-   Prediction/component consistency
-   Alert/work-order consistency
-   Inventory consistency

Create a reusable data-quality report.

The application should surface data-quality problems rather than
silently hiding them.

------------------------------------------------------------------------

# 10. Sensor Telemetry

## 10.1 Minute data

`sensor_reading.csv.gz`

Schema:

``` text
sensor_id
ts
value
```

Purpose:

-   Live-stream simulation
-   Threshold monitoring
-   Fine-grained trend analysis
-   Event generation

## 10.2 Hourly data

`sensor_reading_hourly.csv.gz`

Schema:

``` text
sensor_id
ts
run_fraction
avg_running
min_running
max_running
```

Purpose:

-   12-month model training history
-   Running-only feature engineering
-   Efficient analytics

The hourly dataset retains running/idle context.

Do not use idle periods as if they were sensor health observations.

------------------------------------------------------------------------

# 11. Replay Utility

`replay_to_snowflake.py` is a **demo/live-stream simulator**, not the
production ingestion architecture.

Purpose:

``` text
sensor_reading.csv.gz
      |
      v
timestamp batches
      |
      v
Snowflake SENSOR_READING
```

Each timestamp represents one batch of sensor readings.

The supplied script uses `write_pandas` in small batches and a speedup
parameter.

Example:

``` bash
python replay_to_snowflake.py sensor_reading.csv.gz --speedup 60
```

This simulates approximately one minute of factory time per real second.

The script was written without access to a live Snowflake account, so it
must be tested and adjusted for the target environment.

For production low-latency ingestion, use the appropriate
Snowflake-supported streaming architecture such as Snowpipe Streaming or
an appropriate Kafka integration.

Reference uploaded replay helper: fileciteturn0file0

------------------------------------------------------------------------

# 12. Predictive Maintenance Model

## 12.1 Current baseline

`train_failure_model.py` provides the baseline implementation.

Current design:

-   7-day failure horizon
-   Daily machine-level features
-   Sensor normalization against warning threshold
-   Mean
-   Maximum
-   7-day slope
-   30-day relative change
-   Days since maintenance
-   Failure labels derived from maintenance records
-   Time-based train/test split
-   HistGradientBoostingClassifier
-   Class weighting via sample weights
-   Probability scoring
-   Risk classification
-   Approximate top-feature explanation

Reference uploaded training script: fileciteturn0file1

## 12.2 Failure label

The baseline uses corrective work orders with these degradation-related
codes:

``` text
BD-BRG
BD-MTR
BD-HYD
BD-CLT
BD-DRV
```

Sudden electrical/tooling failures are intentionally excluded from this
baseline.

Preserve this logic unless the model design is intentionally changed.

## 12.3 Model output

Prediction should contain:

``` text
prediction_id
scored_ts
machine_id
suspected_component_id
model_name
horizon_days
failure_prob
risk_level
top_features
```

## 12.4 Risk bands

Current baseline:

``` text
high   >= 0.70
medium >= 0.40 and < 0.70
low    < 0.40
```

These thresholds are application/model configuration, not universal
truths.

## 12.5 Production evolution

The Python script is the baseline/reference implementation.

Target architecture:

``` text
Snowflake telemetry
        |
        v
Feature pipeline / Dynamic Table
        |
        v
Snowflake ML / supported model environment
        |
        v
Model Registry
        |
        v
Prediction table
```

First reproduce the baseline before changing the algorithm.

------------------------------------------------------------------------

# 13. Model Explainability

Current `top_features` are approximate.

They are based on global permutation importance weighted by how unusual
the current feature is.

Do not describe them as exact SHAP values.

CoCo should say:

> "The strongest model signals were..."

not:

> "SHAP proves that..."

unless exact SHAP-based explainability is later implemented.

------------------------------------------------------------------------

# 14. Alerts

Current alert sources:

1.  Threshold exceeded
2.  Predicted failure
3.  Life expiry

The `alert` table is a persistent operational table, not just a view.

Important fields include:

``` text
alert_id
machine_id
component_id
sensor_id
ts
severity
alert_type
reading_value
threshold_value
message
status
priority_score
recommended_action
assigned_to
production_order_id
acknowledged_by
acknowledged_ts
closed_ts
wo_id
```

## 14.1 Current status values

Historical data currently uses:

``` text
open
acknowledged
closed
```

This is sufficient for the initial product.

Do NOT regenerate the historical dataset merely to add workflow states.

## 14.2 Future workflow

The application layer may extend the workflow to:

``` text
OPEN
ACKNOWLEDGED
INVESTIGATING
ACTION_PROPOSED
APPROVED
WORK_ORDER_CREATED
RESOLVED
CLOSED
```

Prefer implementing this as an application/workflow layer rather than
rewriting historical source data.

Recommended future table:

``` text
APP.ALERT_WORKFLOW
```

Potential fields:

``` text
alert_id
stage
assigned_to
started_at
updated_at
approved_by
approved_at
wo_id
resolution
```

This preserves historical truth while allowing the product workflow to
evolve.

------------------------------------------------------------------------

# 15. Alert Generation

## 15.1 Threshold alerts

Concept:

``` text
sensor_reading
   |
   v
threshold evaluation
   |
   v
alert
```

Use Streams + Tasks or another supported event-processing pattern.

Avoid duplicate open alerts for the same sensor/severity unless the
business rule explicitly allows them.

## 15.2 Prediction alerts

Concept:

``` text
prediction
   |
failure_prob crosses configured threshold
   |
predicted_failure alert
```

Do not repeatedly create identical alerts on every score.

Track the transition/crossing event.

## 15.3 Life-expiry alerts

Concept:

``` text
component lifecycle
   |
projected end of life
   |
alert
```

------------------------------------------------------------------------

# 16. Knowledge Layer

Use:

### `maintenance_log`

Technician notes including:

-   Root cause
-   Fault class
-   Symptom
-   Action taken
-   Early warning
-   Note text

### `knowledge_doc`

Manual/SOP excerpts.

Create a Cortex Search corpus over these sources.

The goal is to answer questions such as:

-   What usually causes this failure?
-   What did technicians do last time?
-   What does the SOP recommend?
-   Which inspection procedure applies?
-   Have we seen a similar failure before?

------------------------------------------------------------------------

# 17. Semantic / Ontology Layer

Do not expose all raw tables to the agent without semantic guidance.

Core concepts:

``` text
Machine
Component
Sensor
Production Run
Production Order
Downtime Event
Maintenance Work Order
Maintenance Log
Technician
Spare Part
Supplier
Purchase Order
Alert
Prediction
Knowledge Document
```

Relationships:

``` text
Machine HAS Component
Component HAS Sensor
Machine HAS Production Run
Production Run BELONGS TO Production Order
Machine HAS Downtime Event
Machine HAS Work Order
Work Order HAS Maintenance Log
Work Order USES Spare Part
Spare Part HAS Supplier
Machine HAS Prediction
Prediction MAY_CREATE Alert
Alert MAY_CREATE Work Order
```

Create semantic views / structured tools that expose business concepts
rather than forcing the agent to infer every join.

------------------------------------------------------------------------

# 18. CoCo Agent Responsibilities

CoCo should:

1.  Understand user intent.
2.  Decide which data/tool sources are required.
3.  Query structured Snowflake data.
4.  Search maintenance history and documents.
5.  Combine evidence.
6.  Explain findings.
7.  Identify uncertainty.
8.  Recommend an action.
9.  Ask for approval before operational actions.
10. Execute only explicitly permitted actions.
11. Record action/audit information.

CoCo should not:

-   Invent sensor values
-   Invent maintenance history
-   Invent document contents
-   Claim a manual says something unless retrieved
-   Change the predictive model output
-   Treat synthetic model performance as real-world performance
-   Create operational work orders silently
-   Execute destructive actions without authorization

------------------------------------------------------------------------

# 19. Evidence-Backed Agent Responses

CoCo responses should distinguish:

``` text
PREDICTION
DATA
DOCUMENT
HISTORICAL EVIDENCE
RECOMMENDATION
```

Example structure:

``` text
Risk
M21 has a high modeled probability of degradation-type failure within 7 days.

Sensor evidence
The strongest model signals are abnormal vibration features.

Maintenance evidence
Previous maintenance records show bearing-related intervention.

Knowledge evidence
The relevant maintenance procedure recommends bearing inspection.

Inventory evidence
The compatible bearing is currently unavailable.

Production impact
A production order is scheduled on M21.

Recommendation
Inspect the bearing assembly and assess procurement urgency.
```

Do not blend unsupported claims into a single opaque paragraph.

------------------------------------------------------------------------

# 20. Agent Tooling

Initial tools:

## Structured analytics tools

-   Get machine health
-   Get machine sensor trends
-   Get prediction
-   Get active alerts
-   Get maintenance history
-   Get downtime history
-   Get production impact
-   Get spare inventory
-   Get purchase-order status
-   Get similar failures

## Search tools

-   Search maintenance logs
-   Search manuals/SOPs
-   Search similar historical failures

## Action tools

Initially approval-gated:

-   Create work-order proposal
-   Create maintenance work order
-   Assign alert
-   Acknowledge alert
-   Update workflow stage

Later:

-   Procurement request
-   Part reservation
-   Escalation
-   CMMS integration

------------------------------------------------------------------------

# 21. Human-in-the-Loop Policy

For the first product version:

``` text
CoCo investigates
       |
       v
CoCo recommends
       |
       v
Human approves
       |
       v
Action executes
```

Do not allow an LLM to independently create consequential
maintenance/procurement actions in the first production version.

------------------------------------------------------------------------

# 22. Work-Order Lineage

Maintain lineage:

``` text
prediction_id
     |
     v
alert_id
     |
     v
investigation_id
     |
     v
action_id
     |
     v
wo_id
     |
     v
maintenance_log
```

The system should be able to answer:

> Why was this work order created?

and provide the prediction, alert, evidence, recommendation, approval,
and resulting work order.

------------------------------------------------------------------------

# 23. Streamlit Product UI

Build a real product UI, not a chat-only page.

## 23.1 Factory Overview

Display:

-   Overall factory health
-   OEE
-   Active alerts
-   High-risk machines
-   Production at risk
-   Open work orders
-   Downtime
-   Maintenance workload

## 23.2 Machine 360

For each machine:

-   Health status
-   Failure risk
-   Suspected component
-   Sensor trends
-   Active alerts
-   Prediction history
-   Maintenance history
-   Downtime
-   Production impact
-   Spare-part availability
-   Recent work orders

## 23.3 CoCo Investigation

Primary conversational interface.

Example:

> Why is M21 at risk?

Show:

-   Answer
-   Evidence
-   Sensor signals
-   Prediction
-   Maintenance history
-   Search results
-   Inventory
-   Production impact
-   Recommendation
-   Action controls

## 23.4 Alerts

Display:

-   Alert
-   Machine
-   Component
-   Severity
-   Priority
-   Type
-   Status
-   Owner
-   Recommendation
-   Production order at risk
-   Related prediction
-   Related work order

## 23.5 Work Orders

Display:

-   Work order
-   Machine
-   Component
-   Source
-   Prediction
-   Alert
-   Technician
-   Parts
-   Cost
-   Status
-   Timeline

## 23.6 Chat

Allow natural-language questions over the factory.

Examples:

``` text
Which machines are at high risk today?

Why is M21 at risk?

What happened to M21 the last time its bearing failed?

Do we have the required bearing in stock?

Which production orders could be affected?

What are the top causes of downtime this month?

Show me machines with repeated coolant problems.

Which alerts have not been acknowledged?

What maintenance is due soon?
```

------------------------------------------------------------------------

# 24. Canonical Agent Demonstrations

## Scenario A: M21

Question:

> Why is M21 at risk and what should we do?

Expected chain:

``` text
prediction
 -> sensor evidence
 -> component
 -> maintenance history
 -> technician notes
 -> SOP
 -> spare inventory
 -> supplier
 -> production impact
 -> recommendation
 -> approval-gated work order
```

## Scenario B: M15

Motor degradation.

Use RPM/winding-temperature-related evidence, historical maintenance,
motor component, inventory and production impact.

## Scenario C: M05

Coolant degradation.

Use coolant-flow evidence, maintenance history, relevant SOP,
spare/maintenance context and production impact.

------------------------------------------------------------------------

# 25. Real-Time Demonstration

Use `replay_to_snowflake.py` to simulate:

``` text
minute sensor feed
       |
       v
Snowflake
       |
       v
threshold detection
       |
       v
alert
       |
       v
ML scoring
       |
       v
prediction
       |
       v
CoCo investigation
       |
       v
recommendation
```

The replay utility is a demonstration mechanism.

Production should use a real streaming ingestion architecture.

------------------------------------------------------------------------

# 26. Production / Live Factory Architecture

The conceptual architecture should remain stable.

Only the upstream data sources change.

## Current prototype

``` text
CSV
Python replay
Synthetic ERP
Synthetic maintenance
        |
        v
Snowflake
```

## Real factory

``` text
PLC / SCADA
MES
CMMS / EAM
ERP
IoT
Warehouse / procurement
Technician systems
        |
        v
Streaming / connectors / batch
        |
        v
Snowflake
        |
        v
CoCo
```

Do not redesign CoCo when live data arrives.

------------------------------------------------------------------------

# 27. Real-World Data Requirements

When integrating a real factory, expect to need:

## Telemetry

-   PLC/SCADA/IoT connectivity
-   OPC-UA/MQTT/Kafka or appropriate source
-   Sampling-rate mapping
-   Units
-   Calibration metadata
-   Quality flags
-   Timestamp normalization
-   Late-event handling
-   Duplicate handling

## Asset hierarchy

Potentially:

``` text
Enterprise
Site
Area
Line
Machine
Subsystem
Component
Sensor
```

## Identity mapping

Map external identifiers from:

-   PLC
-   SCADA
-   MES
-   CMMS
-   ERP
-   Snowflake

Example:

``` text
external_asset_id
internal_machine_id
source_system
```

## Enterprise integrations

Potential systems include:

-   SAP
-   Oracle
-   Microsoft Dynamics
-   IBM Maximo
-   MES
-   CMMS/EAM
-   Procurement platforms

Do not assume a specific system until the target factory is known.

------------------------------------------------------------------------

# 28. Real-World ML Requirements

The synthetic model is a baseline.

For real deployment:

-   Validate on actual factory signals
-   Establish proper train/validation/test periods
-   Monitor precision/recall/PR-AUC
-   Monitor false alert rate
-   Monitor lead time
-   Monitor calibration
-   Measure performance by machine and failure type
-   Detect concept drift
-   Version models
-   Monitor feature drift
-   Retrain under controlled governance

Do not advertise synthetic AUC as real-world accuracy.

------------------------------------------------------------------------

# 29. Governance and Security

Implement:

-   Snowflake role-based access
-   Least privilege
-   User-specific permissions
-   Agent tool permissions
-   Approval gates
-   Audit logs
-   Action lineage
-   Data masking where required
-   Sensitive-data handling
-   Environment separation

Recommended environments:

``` text
DEV
TEST
PROD
```

Do not connect production operational systems directly to development
agents.

------------------------------------------------------------------------

# 30. Agent Audit Trail

Create an application audit table, conceptually:

``` text
APP.AGENT_AUDIT
```

Fields may include:

``` text
interaction_id
timestamp
user_id
question
agent_session_id
tools_used
data_sources
evidence_summary
recommendation
action_requested
approval_status
action_result
```

The system must make it possible to understand what CoCo did and why.

------------------------------------------------------------------------

# 31. Alert Workflow Evolution

Do not modify historical source data just to add future workflow states.

Current historical data:

``` text
open
acknowledged
closed
```

is valid.

Application workflow can evolve separately:

``` text
open
 -> acknowledged
 -> investigating
 -> action_proposed
 -> approved
 -> work_order_created
 -> resolved
 -> closed
```

Keep the original alert record as historical evidence.

------------------------------------------------------------------------

# 32. Recommended Build Phases

## Phase 0: Data audit

-   Validate all 19 tables
-   Validate telemetry
-   Validate timestamps
-   Validate keys
-   Validate relationships
-   Validate duplicates
-   Validate gaps
-   Validate model labels

Deliverable:

`DATA_QUALITY_REPORT`

## Phase 1: Snowflake foundation

-   Database
-   Schemas
-   Warehouses
-   Stage
-   File formats
-   RAW tables
-   Bulk loading
-   CORE tables
-   Data-quality SQL

Deliverable:

`COCO_FACTORY` database populated.

## Phase 2: Analytics

Build:

-   Machine health
-   OEE
-   Downtime
-   Production risk
-   Maintenance analysis
-   Inventory risk

Deliverable:

`ANALYTICS` layer.

## Phase 3: ML

-   Reproduce Python baseline
-   Validate results
-   Create feature pipeline
-   Move toward Snowflake ML
-   Model registry
-   Prediction generation

Deliverable:

Production-style `ML.PREDICTION`.

## Phase 4: Knowledge

-   Cortex Search over maintenance logs
-   Cortex Search over knowledge docs
-   Test retrieval quality

Deliverable:

Factory knowledge retrieval.

## Phase 5: Agent

-   Semantic structured data layer
-   Cortex Agent
-   Structured tools
-   Search tools
-   Prediction/alert tools
-   Evidence-backed responses

Deliverable:

Functional CoCo agent.

## Phase 6: Actions

-   Alert workflow
-   Approval UI
-   Work-order proposals
-   Controlled work-order creation
-   Audit trail

Deliverable:

Agentic maintenance workflow.

## Phase 7: Streamlit

-   Factory overview
-   Machine 360
-   Alerts
-   Investigations
-   Work orders
-   Chat
-   Approvals

Deliverable:

Full CoCo product UI.

## Phase 8: Live simulation

-   Replay telemetry
-   Verify alert generation
-   Verify scoring
-   Verify agent investigation

Deliverable:

End-to-end live-style demonstration.

## Phase 9: Real factory readiness

-   Real telemetry connectors
-   MES
-   CMMS/EAM
-   ERP
-   Procurement
-   Identity mapping
-   RBAC
-   Model monitoring
-   Production governance

------------------------------------------------------------------------

# 33. Development Principles

## Principle 1: Data first

Do not build agent logic around unvalidated data.

## Principle 2: ML is not the LLM

Prediction belongs to the predictive model.

## Principle 3: Evidence before explanation

CoCo should retrieve evidence before making operational claims.

## Principle 4: Human approval for consequential actions

The first production version should be human-in-the-loop.

## Principle 5: Preserve historical truth

Do not rewrite historical source data to accommodate new application
workflows.

## Principle 6: Build for replacement

Synthetic data must be replaceable by real sources without redesigning
the product.

## Principle 7: Traceability

Every recommendation should be explainable through data/evidence
lineage.

## Principle 8: Don't over-engineer the prototype

The synthetic dataset is sufficient for building the product. Do not
delay implementation by attempting to simulate every production concern.

------------------------------------------------------------------------

# 34. Definition of Done

The project is considered functionally complete when a user can:

1.  Open CoCo in Streamlit.
2.  See factory health.
3.  See machines and their health.
4.  See active alerts.
5.  Ask a natural-language question.
6.  CoCo retrieves structured Snowflake data.
7.  CoCo retrieves relevant maintenance/manual knowledge.
8.  CoCo uses ML predictions where relevant.
9.  CoCo combines the evidence.
10. CoCo explains the result.
11. CoCo identifies production impact.
12. CoCo checks spare-part availability.
13. CoCo proposes a maintenance action.
14. User approves the action.
15. CoCo creates/records the work-order action.
16. The action is auditable.
17. Replay can demonstrate new telemetry entering the system.
18. The complete chain from telemetry → prediction → alert →
    investigation → action is visible.

------------------------------------------------------------------------

# 35. Example End-to-End User Journey

### User

> Why is M21 at risk?

### CoCo

1.  Reads current prediction.
2.  Identifies M21 as high risk.
3.  Identifies suspected bearing component.
4.  Reads relevant sensor trends.
5.  Finds strongest model features.
6.  Searches previous maintenance notes.
7.  Searches relevant SOP/manual.
8.  Checks current spare inventory.
9.  Checks purchase orders.
10. Checks production orders.
11. Summarizes evidence.
12. Recommends bearing inspection.
13. Offers an approval-gated work order.

### User

> Create the work order.

### CoCo

1.  Shows proposed work order.
2.  Shows machine/component.
3.  Shows reason and prediction.
4.  Shows recommended action.
5.  Shows required parts.
6.  Requests confirmation if required.
7.  Creates/records the action through the approved tool.
8.  Returns the resulting work-order ID.
9.  Records the action in the audit trail.

------------------------------------------------------------------------

# 36. Non-Goals for the Initial Version

Do not initially attempt:

-   Fully autonomous maintenance execution
-   Fully autonomous procurement
-   Fine-tuning a custom LLM
-   Replacing the CMMS
-   Replacing the ERP
-   Replacing the MES
-   Claiming production-grade predictive accuracy from synthetic data
-   Building a generalized factory platform for every industry
    immediately
-   Supporting every possible connector before the core workflow works

Build the core reliability workflow first.

------------------------------------------------------------------------

# 37. Final Product Vision

CoCo should evolve from:

``` text
Factory chatbot
```

into:

``` text
Factory intelligence system
```

and eventually:

``` text
Factory reliability agent
```

The long-term loop is:

``` text
SENSE
  |
  v
UNDERSTAND
  |
  v
PREDICT
  |
  v
INVESTIGATE
  |
  v
RECOMMEND
  |
  v
APPROVE
  |
  v
ACT
  |
  v
VERIFY
  |
  v
LEARN
```

The system should connect machine signals to business consequences and
operational action.

The key product question is not merely:

> "What does the sensor say?"

It is:

> **"What is happening, why is it happening, what will it affect, what
> evidence supports that conclusion, and what should the factory do
> next?"**

That is the purpose of CoCo.

------------------------------------------------------------------------

# 38. Immediate Antigravity Execution Order

Antigravity should implement in this exact broad order:

``` text
1. Inspect repository and existing CoCo implementation
2. Inspect this agent.md
3. Inspect all 19 dataset tables/files
4. Validate schema and relationships
5. Create Snowflake configuration layer
6. Create Snowflake database/schema/stage/format DDL
7. Create RAW loading pipeline
8. Create CORE/conformed model
9. Create data-quality checks
10. Create analytics layer
11. Integrate baseline failure model
12. Create prediction pipeline
13. Create alert pipeline
14. Create knowledge/search layer
15. Create semantic structured-data layer
16. Create Cortex Agent integration
17. Create agent tools
18. Create human approval/action workflow
19. Build Streamlit Factory Overview
20. Build Machine 360
21. Build Alerts
22. Build Investigation
23. Build Work Orders
24. Build Chat
25. Integrate replay utility
26. Test complete telemetry-to-action flow
27. Add automated tests
28. Add logging/audit
29. Add environment configuration
30. Produce setup/run documentation
```

Do not skip directly to UI polish.

Do not hard-code credentials.

Do not commit secrets.

Do not fabricate Snowflake APIs or syntax. Where platform
syntax/features may have changed, verify against current Snowflake
documentation before implementation.

------------------------------------------------------------------------

# 39. Expected Repository Structure

Target a structure approximately like:

``` text
coco/
|
+-- app/
|   +-- streamlit_app.py
|   +-- pages/
|   +-- components/
|   +-- services/
|
+-- agent/
|   +-- coco_agent.py
|   +-- prompts/
|   +-- tools/
|   +-- workflows/
|
+-- snowflake/
|   +-- database/
|   +-- raw/
|   +-- core/
|   +-- analytics/
|   +-- ml/
|   +-- knowledge/
|   +-- app/
|
+-- ml/
|   +-- train_failure_model.py
|   +-- features/
|   +-- evaluation/
|
+-- ingestion/
|   +-- replay_to_snowflake.py
|   +-- loaders/
|
+-- tests/
|   +-- data_quality/
|   +-- ml/
|   +-- agent/
|   +-- integration/
|
+-- docs/
|   +-- architecture.md
|   +-- ontology.md
|   +-- agent-workflows.md
|
+-- .env.example
+-- requirements.txt
+-- README.md
+-- agent.md
```

Adapt this structure to the existing repository rather than blindly
duplicating modules.

------------------------------------------------------------------------

# 40. Antigravity Working Rules

When implementing:

1.  Inspect existing code before creating new code.
2.  Reuse existing repositories/services where appropriate.
3.  Do not create duplicate Snowflake connection layers.
4.  Do not hard-code credentials.
5.  Use environment variables/secrets.
6.  Keep SQL version-controlled.
7.  Keep model training reproducible.
8.  Keep data-loading idempotent where possible.
9.  Add tests for important transformations.
10. Add error handling around Snowflake and agent calls.
11. Log failures clearly.
12. Keep operational actions approval-gated.
13. Preserve source data.
14. Do not silently change schemas.
15. Document any schema migration.
16. Prefer small, testable modules.
17. Build vertical slices that can be executed end-to-end.
18. Validate each phase before moving to the next.
19. Do not fabricate platform features.
20. If Snowflake syntax/API availability is uncertain, verify current
    official documentation.
21. Do not replace the predictive model with an LLM.
22. Do not expose raw database complexity unnecessarily to the user.
23. Keep CoCo responses evidence-backed.
24. Make every consequential agent action auditable.
25. Optimize for a real product, not a one-off demo.

------------------------------------------------------------------------

# 41. First Vertical Slice

Before implementing the entire platform, make this one scenario work
end-to-end:

``` text
M21
 |
 v
prediction
 |
 v
high-risk detection
 |
 v
sensor evidence
 |
 v
maintenance history
 |
 v
Cortex Search
 |
 v
SOP/manual
 |
 v
spare inventory
 |
 v
production impact
 |
 v
CoCo explanation
 |
 v
recommended bearing inspection
 |
 v
human approval
 |
 v
work-order proposal
```

Once this works reliably, generalize the architecture to M15, M05, and
the rest of the factory.

------------------------------------------------------------------------

# 42. Success Criteria for the First Release

The first release should demonstrate:

### Data

-   All 19 tables loaded into Snowflake.
-   Telemetry loaded correctly.
-   Relationships validated.

### Analytics

-   Machine health.
-   OEE/downtime.
-   Maintenance history.
-   Production impact.
-   Inventory.

### ML

-   Baseline model reproduced.
-   Predictions stored in Snowflake.
-   Risk displayed.

### Knowledge

-   Maintenance notes searchable.
-   Manuals/SOPs searchable.

### Agent

-   CoCo can answer structured questions.
-   CoCo can investigate a predicted failure.
-   CoCo combines structured + unstructured evidence.
-   CoCo provides grounded recommendations.

### Actions

-   Approval-gated work-order workflow.
-   Audit trail.

### UI

-   Factory dashboard.
-   Machine 360.
-   Alerts.
-   Investigation.
-   Work orders.
-   Chat.

### Live simulation

-   Replay utility feeds telemetry.
-   Alerts react to new data.
-   CoCo can investigate resulting risk.

------------------------------------------------------------------------

# 43. Final Instruction to the Implementing Agent

Build CoCo as a **real, modular, extensible factory intelligence
product**.

The current synthetic dataset is the development and demonstration
environment.

Snowflake is the system of record and intelligence platform.

Cortex capabilities provide structured analysis, retrieval, and agent
orchestration.

The predictive model is a separate ML component.

Streamlit is the human interface.

CoCo is the agentic reasoning and action layer.

Keep historical data intact.

Allow application workflow states to evolve independently.

Use human approval for consequential actions.

Make evidence and lineage visible.

Design the interfaces so that synthetic CSV files can later be replaced
by real PLC/SCADA/MES/CMMS/ERP/IoT integrations without redesigning the
product.

**Build the product in layers, validate each layer, and make the M21
predictive-maintenance investigation the first complete vertical
slice.**
