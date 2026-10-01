# Milestone 4: CoCo Investigation Layer

## 1. Objective
Establish an autonomous, governed, and mathematically grounded **CoCo Investigation Layer** for the Snowflake Factory Reliability Command Center. Milestone 4 implements the **INVESTIGATE $\rightarrow$ RECOMMEND** phase within the canonical reliability loop:

$$\text{SENSE} \rightarrow \text{UNDERSTAND} \rightarrow \text{PREDICT} \rightarrow \mathbf{\text{INVESTIGATE}} \rightarrow \mathbf{\text{RECOMMEND}} \rightarrow \text{APPROVE} \rightarrow \text{ACT} \rightarrow \text{VERIFY} \rightarrow \text{LEARN}$$

This milestone provides autonomous cross-domain evidence correlation over physical OT telemetry, machine hierarchy, predictive failure signals, maintenance logs, spare parts inventory, and production schedule exposure while strictly preserving a **read-only governance boundary**.

---

## 2. Core Governance & Security Architecture

Milestone 4 enforces strict non-negotiable operational firewalls:

1. **Read-Only Tool Classification:**
   * Every tool registered for autonomous investigation strictly declares `tool_mode = ToolMode.READ`, `mode = "READ"`, and `authorization_boundary = "READ_ONLY"`.
   * Mutating scopes (`action`, `write`, `admin`) are unconditionally blocked by the `M4InvestigationToolRegistry` action firewall.
2. **Prohibition of Mutating Actions (M5 Firewall):**
   * CoCo cannot create work orders, approve actions, assign technicians, purchase spare parts, alter inventory, change production schedules, or start/stop machines.
   * Attempting to register any action or mutator tool immediately raises `ActionFirewallError`.
3. **Prohibition of Arbitrary SQL:**
   * Unrestricted database access (`execute_sql`, `run_query`, `raw_sql`) is strictly prohibited. CoCo interacts exclusively through typed, business-level read tools with bounded inputs and schemas.
4. **Advisory Recommendation Guarantee:**
   * Every recommendation generated in Milestone 4 must have `status = 'ADVISORY'`.
   * Recommendations suggest verifiable next steps (e.g. non-invasive inspection, checklist items) but never claim executed, dispatched, or scheduled operational interventions.
5. **Anti-Hallucination Evidence Grounding:**
   * Every claim in a `Finding` or `Recommendation` must cite explicit `evidence_refs` matching `evidence_id`s in the collected evidence bundle.
   * Inventing evidence IDs, hallucinating machine/component IDs, or generating ungrounded facts raises `AntiHallucinationError`.

---

## 3. Investigation Tool Catalog

The governed Milestone 4 registry exposes 13 typed, read-only tools:

| Tool Name | Domain / Scope | Purpose | Input Schema | Output Schema | Mode |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `get_prediction` | `prediction:read` | Retrieve failure prediction, horizon, and probability | `GetPredictionInput` | `PredictionOutput` | `READ` |
| `get_prediction_lineage` | `prediction:read` | Retrieve inference lineage, model version, and feature snapshot ID | `GetPredictionLineageInput` | `PredictionLineageOutput` | `READ` |
| `get_prediction_feature_snapshot` | `prediction:read` | Retrieve immutable snapshot of feature values used for scoring | `GetFeatureSnapshotInput` | `FeatureSnapshotOutput` | `READ` |
| `get_sensor_context` | `telemetry:read` | Calibrated sensor thresholds, stats, exceedances, and trends | `GetSensorContextInput` | `SensorContextOutput` | `READ` |
| `get_machine_context` | `asset:read` | Physical machine hierarchy, components, and line topology | `GetMachineContextInput` | `MachineContextOutput` | `READ` |
| `get_machine_health` | `asset:read` | Machine health score, health status, and active anomalies | `GetMachineHealthInput` | `MachineHealthOutput` | `READ` |
| `get_maintenance_history` | `maintenance:read` | Historical work orders, repair costs, and technician logs | `GetMaintenanceHistoryInput` | `MaintenanceHistoryOutput` | `READ` |
| `get_historical_failures` | `reliability:read` | Historical component failures and recurrence pattern analysis | `GetHistoricalFailuresInput` | `HistoricalFailuresOutput` | `READ` |
| `get_downtime_history` | `analytics:read` | Categorized downtime minutes, breakdown duration, and stoppage causes | `GetDowntimeHistoryInput` | `DowntimeHistoryOutput` | `READ` |
| `get_inventory_risk` | `supply_chain:read` | Stock on hand, reorder points, supplier lead times, and open POs | `GetInventoryRiskInput` | `InventoryRiskOutput` | `READ` |
| `get_production_context` | `production:read` | Active batch production, remaining quantities, and revenue exposure | `GetProductionContextInput` | `ProductionContextOutput` | `READ` |
| `search_knowledge` | `knowledge:read` | Semantic/keyword search across technical manuals and ISO guidelines | `SearchKnowledgeInput` | `SearchKnowledgeOutput` | `READ` |
| `get_knowledge_document` | `knowledge:read` | Full-text retrieval of specific engineering procedures and documents | `GetKnowledgeDocumentInput` | `KnowledgeDocumentOutput` | `READ` |

---

## 4. Evidence Model & Provenance

Every piece of evidence collected by CoCo is modeled as an immutable `Evidence` record with cryptographic or deterministic provenance:

```python
class Evidence(BaseModel):
    evidence_id: str             # e.g., 'EV-PRED-179063', 'EV-INV-SP-002'
    investigation_id: str        # Unique investigation identifier
    evidence_type: str           # PREDICTION, TELEMETRY, INVENTORY, PRODUCTION, etc.
    category: str                # Standardized investigation category
    source: str                  # Governed Snowflake table or corpus reference
    source_type: str             # PREDICTION, SENSOR, SPARE_PART, PRODUCTION_ORDER, etc.
    source_id: str               # Target primary key identifier
    metric: str                  # Signal or metric name
    observed_value: Any          # Quantified value
    unit: Optional[str]          # mm/s, degC, INR, units, etc.
    severity: Optional[str]      # CRITICAL, HIGH, MEDIUM, LOW
    relationship: str            # SUPPORTS, CONTEXTUAL, CONTRADICTS
    machine_id: str              # Target asset ID
    component_id: Optional[str]  # Target component ID
    claim: str                   # Factual statement directly verified by source
    summary: str                 # Readable summary of observed fact
    timestamp: datetime          # Observation or scoring timestamp
```

Findings and Recommendations reference these IDs:
* `Finding.evidence_refs = ["EV-PRED-001", "EV-S-M21-VIB-01"]`
* `Recommendation.evidence_refs = ["EV-PRED-001", "EV-INV-SP-002", "EV-PROD-PRD-01278"]`

---

## 5. Investigation Service Architecture

The `InvestigationService` coordinates the full autonomous lifecycle:

```
Trigger (PREDICTION, MACHINE, USER_QUERY)
                   │
                   ▼
       Trigger Resolution & Asset Validation
                   │
                   ▼
     Cross-Domain Evidence Retrieval (Typed Read Tools)
   ├─ Prediction & Lineage Context
   ├─ Physical Telemetry & Threshold Exceedances
   ├─ Machine & Component Topology
   ├─ Maintenance History & Recurrence Patterns
   ├─ Spare Part Inventory & Stockout Exposure
   ├─ Production Schedule & Unfulfilled Revenue
   └─ Engineering Manuals & ISO References
                   │
                   ▼
        InvestigationContext Bundle
                   │
                   ▼
   CoCo Reasoning Adapter (Deterministic / Live Cortex)
   ├─ Hypotheses Formulation (Supported vs Refuted)
   ├─ Findings Synthesis (Observed Facts vs Inferences)
   └─ Advisory Recommendations (Checklists, Downtime Est.)
                   │
                   ▼
     Deterministic Anti-Hallucination Validation
   ├─ Evidence Reference Verification
   ├─ Asset & Component Grounding
   ├─ Non-Advisory Status Rejection
   └─ Action Claim Rejection
                   │
                   ▼
       Repository & Snowflake Persistence
```

---

## 6. Snowflake Persistence (`COCO_FACTORY.APP`)

Six new application and audit tables were added to `snowflake/ddl/coco_factory/60_app_foundation.sql`:

1. `COCO_FACTORY.APP.INVESTIGATION`: Master investigation record, trigger details, failure mode, confidence, and lifecycle timestamps.
2. `COCO_FACTORY.APP.INVESTIGATION_EVIDENCE`: Fact-grounded evidence store with metric values, units, sources, and claims.
3. `COCO_FACTORY.APP.INVESTIGATION_HYPOTHESIS`: Evaluated failure hypotheses, confidence scores, and supporting/contradicting evidence IDs.
4. `COCO_FACTORY.APP.INVESTIGATION_FINDING`: Correlated investigation findings, facts, inferences, and evidence references.
5. `COCO_FACTORY.APP.INVESTIGATION_RECOMMENDATION`: Governed advisory recommendations, suggested checklists, downtime estimates, and parts.
6. `COCO_FACTORY.APP.INVESTIGATION_TOOL_CALL`: Complete audit log of every read tool executed (latency, parameters, record count, success).

---

## 7. M21 Canonical Investigation Spotlight

The end-to-end acceptance test (`test_m21_investigation_scenario.py`) validates the autonomous investigation of spotlight machine **M21 (Grinder 3)**:

* **Trigger:** Machine `M21`, Prediction `PRED-000322`
* **Target Component:** `C-M21-BRG` (Drive-End Bearing 6206-2RS)
* **Predictive Signal:** $P(\text{failure}) \approx 0.9547$, `CRITICAL` risk level, 7-day failure horizon.
* **Telemetry Evidence:**
  * Vibration sensor `S-M21-VIB`: Warning limit 2.8 mm/s, Critical 4.5 mm/s $\rightarrow$ Observed **4.881 mm/s** (`CRITICAL_SPIKE`).
  * Bearing temperature `S-M21-BTMP`: Warning limit 75.0°C, Critical 90.0°C $\rightarrow$ Observed **84.55°C** (Elevated thermal rise).
* **ML Features:** `VIB_max = 1.743`, `VIB_mean = 1.250`, `VIB_rel30 = 1.480`, `days_since_last_maintenance = 65.0`.
* **Supply Chain Evidence:**
  * Spare part `SP-002` (Drive-End Bearing 6206-2RS): **0 units on hand** (Critical stockout).
  * Reorder level: 2 units.
  * Supplier `SUP-12` (Vertex Industrial Supplies / Apex Precision Bearings): **5 days lead time**.
* **Production Exposure:**
  * Active order `PRD-01278` on Line L5: **211 units remaining** of Product `P008` (Mounting Flange MF-25).
  * Unit Price: ₹394.00.
  * Unfulfilled Revenue Exposure: **₹83,134.00**.
* **Historical Maintenance:** Work order `WO-000523`, failure code `BD-BRG` (Drive-end bearing replacement).
* **Knowledge Guidance:** `DOC-001` (Bearing Troubleshooting Manual) and `DOC-002` (ISO Vibration Severity Standard).
* **Advisory Recommendation:**
  * Action: Physical acoustic inspection and vibration spectrum FFT analysis during shift transition.
  * Status: **`ADVISORY`**.
  * Suggested Parts: `["SP-002"]`.
  * Est. Downtime: 2.0 hours.

---

## 8. Verification Results

```bash
# 1. Full Pytest Suite
python -m pytest
# Result: 212 passed, 1 skipped in 29.42s

# 2. Syntax & Compilation Check
python -m compileall .
# Result: All files compiled successfully with zero syntax errors

# 3. Snowflake DDL Dry Run Validation
python snowflake/scripts/init_coco_factory.py --dry-run
# Result: 10 scripts, 92 statements successfully parsed and validated
```
