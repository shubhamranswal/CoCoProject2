# Industrial Reliability Ontology

**Document:** `architecture/ontology.md`
**Version:** 1.0
**Status:** Foundational Architecture
**Scope:** Factory Reliability Command Center
**Primary Platform:** Snowflake
**Primary Consumers:** Data pipelines, semantic layer, ML models, AI agents, Streamlit application, integrations

---

# 1. Purpose

The Industrial Reliability Ontology defines the common language and relationship model used by the Factory Reliability Command Center.

It describes:

* what entities exist in the industrial environment
* how those entities relate to one another
* what events can happen
* what states entities can occupy
* what observations can be made
* how operational evidence is connected
* how reliability conclusions are represented
* how recommendations become actions
* how actions affect machines and operations
* how outcomes feed back into the intelligence system

The ontology is the conceptual contract between:

```text
Industrial Systems
        ↓
Snowflake Data Platform
        ↓
Analytics / ML
        ↓
Semantic Layer
        ↓
AI Agents
        ↓
Actions
        ↓
Operational Systems
```

Without a common ontology, each layer develops its own interpretation of:

* machine
* failure
* alert
* maintenance
* production
* quality
* work order
* OEE

That creates semantic drift.

This ontology prevents that.

---

# 2. Ontology Design Principles

The ontology follows these principles.

## 2.1 Asset-centric

The machine is the primary operational context.

Most reliability questions eventually resolve to:

```text
What is happening to this asset?
```

---

## 2.2 Event-oriented

Industrial operations are temporal.

The ontology therefore treats events as first-class concepts.

Examples:

```text
MachineStarted
MachineStopped
SensorAnomalyDetected
FailureOccurred
MaintenancePerformed
QualityDeviationDetected
WorkOrderCreated
MachineRecovered
```

---

## 2.3 Evidence-driven

Every reliability conclusion should be traceable to evidence.

```text
Observation
    ↓
Evidence
    ↓
Hypothesis
    ↓
Finding
    ↓
Recommendation
    ↓
Action
    ↓
Outcome
```

---

## 2.4 Temporal

The ontology must preserve:

* event time
* ingestion time
* effective time
* validity period
* historical state

A machine's state at 09:00 cannot be reconstructed from its current state alone.

---

## 2.5 Hierarchical

Industrial assets exist inside physical and organizational hierarchies.

```text
Enterprise
    ↓
Site
    ↓
Plant
    ↓
Area
    ↓
Production Line
    ↓
Machine
    ↓
Component
    ↓
Sensor
```

---

## 2.6 Composable

The ontology should allow new domains to be added without redesigning the entire model.

Future domains may include:

* energy
* supply chain
* workforce
* inventory
* safety
* environmental monitoring

---

## 2.7 System-neutral

The ontology describes business concepts, not source-system schemas.

For example:

```text
WorkOrder
```

is an ontology concept.

It may originate from:

```text
SAP
Maximo
ServiceNow
Custom CMMS
```

The source system should not define the canonical meaning.

---

## 2.8 Action-aware

The ontology must support not only observation and analysis but operational action.

```text
Detect
→ Investigate
→ Decide
→ Approve
→ Execute
→ Verify
```

---

# 3. Ontology Layers

The ontology is organized into eight conceptual layers.

```text
┌─────────────────────────────────────────────┐
│ 8. Governance & Identity                    │
├─────────────────────────────────────────────┤
│ 7. Actions & Outcomes                       │
├─────────────────────────────────────────────┤
│ 6. Intelligence & Reasoning                 │
├─────────────────────────────────────────────┤
│ 5. Maintenance & Reliability                │
├─────────────────────────────────────────────┤
│ 4. Production & Quality                     │
├─────────────────────────────────────────────┤
│ 3. Telemetry & Observations                 │
├─────────────────────────────────────────────┤
│ 2. Assets & Physical Hierarchy              │
├─────────────────────────────────────────────┤
│ 1. Organization & Location                  │
└─────────────────────────────────────────────┘
```

---

# 4. Top-Level Entity Model

The complete conceptual model is:

```text
Organization
    │
    └── Site
          │
          └── Plant
                │
                └── Area
                      │
                      └── Production Line
                            │
                            └── Machine
                                  │
                     ┌────────────┼─────────────┐
                     │            │             │
                 Component      Sensor      Production
                     │            │             │
                     │            ▼             ▼
                     │        Measurement    Production Run
                     │
                     ▼
                  Failure
                     │
                     ▼
              Maintenance Event
                     │
                     ▼
                 Work Order
```

Across this structure:

```text
Machine
  ├── produces → ProductionRun
  ├── has → Sensor
  ├── has → Component
  ├── experiences → Failure
  ├── generates → Observation
  ├── contributes_to → OEE
  └── has → MaintenanceHistory
```

---

# 5. Core Entity Categories

The ontology contains the following entity categories.

## Organizational

* Organization
* Region
* Site
* Plant
* Area
* ProductionLine
* WorkCenter

## Asset

* Asset
* Machine
* Component
* Sensor
* SensorType
* AssetRelationship

## Production

* Product
* ProductionOrder
* ProductionRun
* Operation
* ProcessStep
* Cycle
* DowntimeEvent

## Quality

* QualityInspection
* QualityMeasurement
* Defect
* QualityEvent
* DefectType

## Reliability

* Failure
* FailureMode
* FailureCause
* FailureEffect
* MaintenanceStrategy
* MaintenanceEvent
* MaintenanceTask
* MaintenanceHistory

## Work Management

* WorkOrder
* WorkOrderTask
* Technician
* SparePart
* WorkOrderStatus

## Telemetry

* Measurement
* Signal
* Feature
* Baseline
* OperatingRegime

## Intelligence

* Alert
* Anomaly
* HealthAssessment
* FailureRisk
* Prediction
* Investigation
* Hypothesis
* Evidence
* Finding
* Recommendation
* ConfidenceAssessment

## Actions

* Action
* Approval
* Execution
* Outcome
* Verification

## Knowledge

* Document
* Manual
* Procedure
* EngineeringStandard
* KnowledgeChunk
* KnowledgeRelationship

## OEE

* AvailabilityMetric
* PerformanceMetric
* QualityMetric
* OEEMetric
* OEEImpact

## Agent

* Agent
* AgentExecution
* AgentTool
* ToolCall
* AgentDecision

## Governance

* User
* Role
* Permission
* Policy
* AuditEvent

---

# 6. Organizational Ontology

## 6.1 Organization

Represents the business entity operating one or more industrial facilities.

### Attributes

```text
organization_id
name
industry
timezone
status
created_at
updated_at
```

### Relationships

```text
Organization
    HAS_REGION → Region
    OPERATES → Site
    OWNS → Asset
    HAS_USER → User
    DEFINES → Policy
```

---

# 7. Region

A geographic or operational grouping of sites.

```text
Region
    BELONGS_TO → Organization
    CONTAINS → Site
```

Example:

```text
North India
    ├── Plant Delhi
    ├── Plant Noida
    └── Plant Jaipur
```

---

# 8. Site

Represents a physical industrial location.

A site may contain one or more plants.

```text
Site
    BELONGS_TO → Organization
    LOCATED_IN → Region
    CONTAINS → Plant
```

---

# 9. Plant

The primary operational facility.

```text
Plant
    BELONGS_TO → Site
    CONTAINS → Area
    CONTAINS → ProductionLine
    HAS → WorkCenter
```

### Attributes

```text
plant_id
plant_code
name
timezone
operational_status
```

---

# 10. Area

A logical or physical plant subdivision.

Examples:

```text
Assembly
Machining
Packaging
Heat Treatment
Inspection
Warehouse
```

```text
Area
    BELONGS_TO → Plant
    CONTAINS → ProductionLine
    CONTAINS → Machine
```

---

# 11. Production Line

A connected sequence of production assets used to manufacture a product.

```text
ProductionLine
    BELONGS_TO → Area
    CONTAINS → Machine
    PRODUCES → Product
    EXECUTES → ProductionRun
```

---

# 12. Work Center

Represents an operational work center.

```text
WorkCenter
    BELONGS_TO → Plant
    CONTAINS → Machine
    PERFORMS → Operation
```

---

# 13. Asset Ontology

The asset hierarchy is:

```text
Asset
 ├── Machine
 ├── Component
 └── Sensor
```

All physical equipment inherits from the general `Asset` concept.

---

# 14. Asset

The abstract parent concept for physical industrial equipment.

### Attributes

```text
asset_id
asset_code
name
asset_type
manufacturer
model
serial_number
commission_date
decommission_date
criticality
status
```

### Relationships

```text
Asset
    LOCATED_AT → Plant
    PART_OF → ParentAsset
    CONTAINS → ChildAsset
    HAS_COMPONENT → Component
    HAS_SENSOR → Sensor
```

---

# 15. Machine

A machine is an operational asset capable of performing one or more manufacturing activities.

### Relationships

```text
Machine
    BELONGS_TO → ProductionLine
    HAS_COMPONENT → Component
    HAS_SENSOR → Sensor
    PERFORMS → Operation
    PRODUCES → ProductionRun
    EXPERIENCES → Failure
    HAS → MaintenanceEvent
    HAS → WorkOrder
    CONTRIBUTES_TO → OEEImpact
```

### Machine State

Possible states:

```text
RUNNING
IDLE
STOPPED
FAULTED
MAINTENANCE
STARTING
STOPPING
UNKNOWN
```

---

# 16. Component

A physical subassembly or replaceable machine part.

Examples:

```text
Bearing
Motor
Pump
Gearbox
Valve
Conveyor
Spindle
Cooling System
Hydraulic System
```

```text
Component
    PART_OF → Machine
    HAS_SENSOR → Sensor
    EXPERIENCES → Failure
    REPAIRED_BY → MaintenanceEvent
    REPLACED_BY → MaintenanceEvent
```

---

# 17. Sensor

A physical or logical source of machine measurements.

Examples:

```text
Vibration Sensor
Temperature Sensor
RPM Sensor
Pressure Sensor
Current Sensor
Power Sensor
Flow Sensor
Acoustic Sensor
```

```text
Sensor
    INSTALLED_ON → Machine
    MEASURES → Signal
    GENERATES → Measurement
```

---

# 18. Sensor Type

Defines the semantic meaning of a sensor.

Examples:

```text
VIBRATION
TEMPERATURE
RPM
PRESSURE
CURRENT
POWER
FLOW
ACOUSTIC
POSITION
TORQUE
```

---

# 19. Asset Relationships

Asset relationships should be explicit.

Examples:

```text
Machine A
    PART_OF → Production Line 1

Motor M1
    COMPONENT_OF → Machine M204

Sensor S44
    INSTALLED_ON → Motor M1
```

Relationship types:

```text
PART_OF
CONTAINS
INSTALLED_ON
CONNECTED_TO
DEPENDS_ON
FEEDS
CONTROLS
DRIVES
COOLS
LUBRICATES
```

---

# 20. Telemetry Ontology

Telemetry describes observed machine behavior.

The conceptual hierarchy is:

```text
Sensor
   ↓
Signal
   ↓
Measurement
   ↓
Feature
   ↓
Anomaly
   ↓
HealthAssessment
```

---

# 21. Signal

A continuous or discrete measurable property.

Examples:

```text
Motor Temperature
Bearing Vibration RMS
Motor RPM
Hydraulic Pressure
Electrical Current
Power Consumption
```

### Attributes

```text
signal_id
name
unit
measurement_type
sampling_rate
valid_range
```

---

# 22. Measurement

A timestamped observation.

```text
Measurement
├── measurement_id
├── sensor_id
├── signal_id
├── asset_id
├── timestamp
├── value
├── unit
├── quality
└── source
```

A measurement is a fact.

It is not an interpretation.

---

# 23. Measurement Quality

Measurement quality should be explicit.

Possible values:

```text
VALID
MISSING
SUSPECT
OUT_OF_RANGE
DUPLICATE
ESTIMATED
INTERPOLATED
STALE
```

---

# 24. Feature

A derived numerical representation of one or more measurements.

Examples:

```text
vibration_rms
vibration_peak
temperature_slope
rpm_variance
pressure_stddev
current_mean
temperature_delta
```

Features may be calculated over:

```text
1 minute
5 minutes
15 minutes
1 hour
1 day
```

---

# 25. Baseline

Defines expected machine behavior under a specific operating regime.

A baseline should not assume that:

```text
Machine temperature = 70°C
```

is universally normal.

Instead:

```text
Expected temperature
=
function(machine, operating_regime, load, ambient_conditions)
```

A baseline may therefore be contextual.

---

# 26. Operating Regime

Defines the conditions under which a machine is operating.

Examples:

```text
LOW_LOAD
NORMAL_LOAD
HIGH_LOAD
STARTUP
SHUTDOWN
IDLE
PRODUCT_A
PRODUCT_B
```

This prevents false anomaly detection caused by comparing fundamentally different operating conditions.

---

# 27. Observation

An observation is a detected or calculated fact about an asset or process.

Examples:

```text
Vibration increased 42% from baseline.

Temperature has increased continuously for 8 hours.

RPM variance is above historical range.
```

Observations can be generated from:

* raw telemetry
* analytics
* quality systems
* maintenance records
* operators
* agents

---

# 28. Anomaly

An anomaly represents behavior that deviates materially from expected behavior.

```text
Anomaly
    DETECTED_ON → Machine
    DERIVED_FROM → Measurement
    COMPARED_TO → Baseline
    OCCURS_DURING → OperatingRegime
```

### Attributes

```text
anomaly_id
severity
score
detected_at
start_time
end_time
status
detection_method
```

---

# 29. Reliability Ontology

The reliability model is:

```text
Observation
     ↓
Anomaly
     ↓
FailureRisk
     ↓
FailureMode
     ↓
Failure
     ↓
Maintenance
     ↓
Outcome
```

---

# 30. Failure

A failure is an event in which an asset or component can no longer perform its intended function within defined operating requirements.

A failure must be distinguished from an anomaly.

```text
Anomaly:
Something unusual.

Failure:
Required function is no longer adequately performed.
```

---

# 31. Failure Mode

A specific manner in which an asset can fail.

Examples:

```text
BEARING_DEGRADATION
MOTOR_OVERHEATING
PUMP_CAVITATION
GEARBOX_FAILURE
LUBRICATION_FAILURE
BELT_MISALIGNMENT
VALVE_STUCK
ELECTRICAL_OVERLOAD
```

---

# 32. Failure Cause

Represents the underlying cause associated with a failure.

Examples:

```text
INSUFFICIENT_LUBRICATION
EXCESSIVE_LOAD
MISALIGNMENT
WEAR
CONTAMINATION
ELECTRICAL_FAULT
THERMAL_STRESS
OPERATOR_ERROR
```

Relationship:

```text
Failure
    HAS_MODE → FailureMode
    HAS_CAUSE → FailureCause
```

---

# 33. Failure Effect

Represents the operational consequence of a failure.

Examples:

```text
Machine Stops
Reduced Throughput
Quality Degradation
Production Delay
Safety Risk
Energy Increase
```

---

# 34. Failure Event

A timestamped occurrence of an actual failure.

```text
FailureEvent
    OCCURRED_ON → Machine
    AFFECTED → Component
    HAS_MODE → FailureMode
    HAS_CAUSE → FailureCause
    CAUSED → FailureEffect
```

---

# 35. Failure Signature

A failure signature describes a characteristic pattern associated with a failure mode.

Example:

```text
Bearing degradation

Signature:
    vibration_rms ↑
    vibration_peak ↑
    temperature ↑
    RPM variance ↑
```

A signature may be derived from:

* historical failures
* engineering knowledge
* statistical analysis
* machine learning

---

# 36. Failure Risk

Failure risk represents the estimated likelihood or risk level of a failure occurring within a defined horizon.

Example:

```text
Machine M204

Failure Mode:
Bearing degradation

Risk:
0.87

Prediction Horizon:
72 hours
```

Risk must always have:

```text
asset
failure_mode
prediction_time
horizon
model_version
score
```

---

# 37. Prediction

A prediction is a model-generated estimate about a future or unknown state.

Examples:

```text
Failure probability
Remaining useful life
Expected downtime
Expected quality defect rate
```

---

# 38. Health Assessment

A health assessment summarizes the current condition of an asset.

Example:

```text
Health:
DEGRADING

Health Score:
72/100

Primary Concern:
Bearing

Updated:
2026-09-28T10:15:00
```

Health assessment is a derived state, not a raw measurement.

---

# 39. Maintenance Ontology

Maintenance is represented as:

```text
MaintenanceStrategy
       ↓
MaintenancePlan
       ↓
MaintenanceTask
       ↓
MaintenanceEvent
       ↓
WorkOrder
       ↓
Outcome
```

---

# 40. Maintenance Strategy

Defines how maintenance should be performed for an asset.

Examples:

```text
PREVENTIVE
PREDICTIVE
CORRECTIVE
CONDITION_BASED
INSPECTION_BASED
RUN_TO_FAILURE
```

---

# 41. Maintenance Event

Represents actual maintenance performed.

Examples:

```text
Inspection
Repair
Replacement
Lubrication
Calibration
Cleaning
Alignment
```

Relationships:

```text
MaintenanceEvent
    PERFORMED_ON → Asset
```
