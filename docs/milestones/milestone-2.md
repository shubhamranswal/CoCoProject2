# Milestone 2: Analytics + Knowledge Foundation

## 1. Overview & Objective

Milestone 2 establishes the operational intelligence layer of the **Snowflake H2S Factory Reliability Command Center** per `AGENT.md` v2.0.

Building directly on the conformed data foundation established in Milestone 1, Milestone 2 delivers:
1. **Governed Analytical Views** in schema `COCO_FACTORY.ANALYTICS` for machine health, bounded OEE, multi-category downtime, maintenance cost/MTTR, inventory exposure, and production financial context.
2. **Reliability Feature Pipeline** in schema `COCO_FACTORY.ML` for rolling 7-day signals, 30-day baseline ratios, sensor slopes, and model registry infrastructure.
3. **Structured Knowledge Corpus & Failure Mode Taxonomy** in schema `COCO_FACTORY.KNOWLEDGE` normalizing OEM manuals, SOPs, and engineering reference guides for semantic retrieval and Cortex Search.
4. **Strong Typed Domain Layer & Repository Abstractions** (`AnalyticsRepository`, `KnowledgeSearchRepository`) implemented identically across both `InMemoryRepository` and `SnowflakeRepository`.
5. **M21 Reliability Evidence Chain** connecting telemetry anomalies to predictions, spare part stockouts, customer order revenue exposures, and corrective knowledge SOPs.

---

## 2. Analytical Views Architecture (`COCO_FACTORY.ANALYTICS`)

All analytical views are defined in `snowflake/ddl/coco_factory/30_analytics_foundation.sql`:

### 2.1 `ANALYTICS.MACHINE_HEALTH_DAILY`
* **Purpose**: Daily consolidated health scorecard per machine.
* **Aggregations**:
  * Telemetry volume (`reading_count`), mean/max vibration (`avg_vibration`, `max_vibration`), mean/max temperature (`avg_temperature`, `max_temperature`).
  * Telemetry anomaly count (`exceedance_count`).
  * Daily downtime minutes (`downtime_minutes`) and breakdown count (`breakdown_count`).
  * Closed-loop work orders and active alerts (`open_alerts`).
  * Latest failure probability and risk level joined from `CORE.PREDICTION_LOG`.
* **Health Status Classification**:
  * `CRITICAL`: Active breakdown OR open critical alert OR failure probability \(\ge 0.85\).
  * `DEGRADED`: High risk prediction OR vibration exceedance OR corrective maintenance required.
  * `WARNING`: Open warning alert OR failure probability \(\ge 0.50\).
  * `HEALTHY`: Normal operating band without warning/critical excursions.

### 2.2 `ANALYTICS.MACHINE_OEE_DAILY`
* **Purpose**: Industry-standard Overall Equipment Effectiveness (OEE) with strict boundary enforcement.
* **Mathematical Invariants**:
  $$\text{Availability} = \min\left(1.0, \max\left(0.0, \frac{\text{Operating Minutes}}{\text{Planned Production Minutes}}\right)\right)$$
  $$\text{Performance} = \min\left(1.0, \max\left(0.0, \frac{\text{Total Pieces Produced}}{\text{Ideal Production Capacity}}\right)\right)$$
  $$\text{Quality} = \min\left(1.0, \max\left(0.0, \frac{\text{Good Pieces}}{\text{Total Pieces Produced}}\right)\right)$$
  $$\text{OEE} = \text{Availability} \times \text{Performance} \times \text{Quality} \quad (\in [0.0, 1.0])$$
* **Data Integrity**: Quality is computed strictly from physical counts in `CORE.PRODUCTION_RUN` (`total_count`, `good_count`, `reject_count`), with zero invented or unverified synthetic scrap rates.

### 2.3 `ANALYTICS.DOWNTIME_DAILY`
* **Purpose**: Categorized downtime loss analysis.
* **Loss Categories Tracked**:
  * `breakdown` (unplanned mechanical/electrical failure stops).
  * `minor_stop` (short stoppages \(\le 10\) min, sensor alarms, feed blocks).
  * `changeover` (tooling and product line switchover).
  * `no_material` (upstream supply chain starving).
  * `no_operator` (shift handoff / staffing gaps).
  * `planned_maintenance` (scheduled PM intervals).
* **Metrics**: Total downtime minutes, breakdown event count, total event count, top downtime category, top reason code.

### 2.4 `ANALYTICS.MAINTENANCE_DAILY`
* **Purpose**: Work order throughput, labor allocation, parts cost, and Mean Time to Repair (MTTR).
* **Metrics**:
  * Work order counts by type: `corrective_count`, `preventive_count`, `breakdown_count`.
  * Total labor hours and labor cost (calculated at standard Indian technician rate of ₹750/hr).
  * Total parts cost (summed from `CORE.WO_PART_USAGE`).
  * Total maintenance cost = Parts Cost + Labor Cost.
  * Mean Time to Repair (MTTR in minutes) for resolved corrective work orders.

### 2.5 `ANALYTICS.INVENTORY_RISK`
* **Purpose**: Proactive inventory shortage detection linked to critical machine dependencies.
* **Status Logic**:
  * `STOCKOUT`: $\text{stock\_qty} = 0$.
  * `LOW_STOCK`: $0 < \text{stock\_qty} \le \text{reorder\_level}$.
  * `HEALTHY`: $\text{stock\_qty} > \text{reorder\_level}$.
* **Critical Exposure Flag (`is_critical_exposure`)**:
  * Flagged `TRUE` when a component part is in `STOCKOUT` status and has an active failure prediction or open alert on its corresponding machine.
  * Captures supplier lead time (`lead_time_days`), open purchase order count, and open PO quantity.

### 2.6 `ANALYTICS.PRODUCTION_CONTEXT`
* **Purpose**: Real-time customer delivery risk and revenue exposure quantification.
* **Metrics**:
  * Active order ID, product name, customer name, scheduled due date, days until due.
  * Progress percentage: $\frac{\text{produced\_qty}}{\text{planned\_qty}} \times 100$.
  * Unfulfilled revenue exposure:
    $$\text{Unfulfilled Exposure (INR)} = (\text{planned\_qty} - \text{produced\_qty}) \times \text{unit\_price\_inr}$$

---

## 3. Reliability Feature Engineering (`COCO_FACTORY.ML`)

Defined in `snowflake/ddl/coco_factory/40_ml_foundation.sql`:

* **`ML.MACHINE_FEATURE_DAILY` & `ML.V_MACHINE_FEATURE_DAILY`**:
  * `vib_mean_7d`: Rolling 7-day average vibration velocity RMS.
  * `vib_max_7d`: Rolling 7-day peak vibration velocity RMS.
  * `vib_std_7d`: Rolling 7-day standard deviation of vibration readings.
  * `vib_rel30`: Relative ratio of 7-day mean vibration to the 30-day baseline ($\frac{\text{mean\_7d}}{\text{baseline\_30d}}$).
  * `vib_slope_7d`: 7-day linear trend rate of change.
  * `temp_mean_7d`, `temp_max_7d`, `temp_rel30`: Thermal gradient and baseline escalation metrics.
  * `exceedance_ratio_7d`: Ratio of anomalous/critical excursion minutes to total operating minutes.
  * `downtime_ratio_7d`: Ratio of downtime minutes to planned production minutes.
  * `unplanned_downtime_hours_7d`: Total unplanned hours lost over trailing 7 days.
  * `breakdown_count_30d`: Cumulative breakdown count over 30 days.
  * `days_since_last_maint`: Days elapsed since the most recent completed work order.
* **`ML.MODEL_REGISTRY`**:
  * Tracks deployed failure prediction models (`hgb_failure_7d_v1`, XGBoost, etc.), versioning, hyperparameters, ROC-AUC, F1-scores, and deployment timestamps.
* **`ML.INFERENCE_LOG`**:
  * Audit log for all model scorings, inputs, output probabilities, and latency.

---

## 4. Knowledge Foundation & Semantic Search (`COCO_FACTORY.KNOWLEDGE`)

Defined in `snowflake/ddl/coco_factory/50_knowledge_foundation.sql`:

### 4.1 `KNOWLEDGE.CORPUS`
* Exactly 16 conformed technical documents populated from `CORE.KNOWLEDGE_DOC`:
  * `DOC-001`: Bearing failure troubleshooting guide (Drive-End Bearing).
  * `DOC-002`: Vibration severity reference (ISO 10816 velocity bands: warning 2.8 mm/s, critical 4.5 mm/s).
  * `DOC-003`: Motor overheating and overload guide (Drive Motor).
  * `DOC-004`: Hydraulic pressure loss guide (Hydraulic Pump).
  * `DOC-005`: Coolant flow low alarm guide (Coolant Pump).
  * `DOC-006`: Drive belt and gearbox guide (Gearbox/Drive Belt).
  * `DOC-007`: PLC and electrical fault guide (PLC/Electrical Panel).
  * `DOC-008`: Tooling wear and changeover SOP (Tooling).
  * `DOC-009`: Preventive maintenance checklist - general.
  * `DOC-010`: Condition-based maintenance policy (proactive WO triggers & closed-loop feedback).
  * `DOC-011`: Spare parts criticality and stocking governance.
  * `DOC-012`: OEE loss categories reference guide.
  * `DOC-013` to `DOC-016`: OEM equipment maintenance manuals for injection molding, CNC milling, air compressors, and conveyor drives.

### 4.2 `KNOWLEDGE.FAILURE_MODE_TAXONOMY`
Standardized 10-code failure mode taxonomy seeded with deterministic MERGE:
1. `BD-BRG` - Bearing Breakdown (Mechanical, Drive-End Bearing)
2. `PD-VIB` - Predictive Bearing Degradation (Mechanical, Drive-End Bearing)
3. `BD-MTR` - Motor Winding / Stator Failure (Electrical, Drive Motor)
4. `PD-CUR` - Predictive Motor Current Overload (Electrical, Drive Motor)
5. `BD-HYD` - Hydraulic Pressure Loss (Hydraulic, Hydraulic Pump)
6. `BD-CLT` - Coolant Circulation Failure (Cooling, Coolant Pump)
7. `BD-DRV` - Drive Belt / Gearbox Mechanical Wear (Mechanical, Gearbox/Drive Belt)
8. `BD-ELC` - Electrical Panel / PLC Fault (Electrical, PLC/Electrical Panel)
9. `BD-TLG` - Tooling Wear & Dimension Drift (Tooling, Tooling)
10. `PM-ROUTINE` - Scheduled Preventive Maintenance (Preventive, General)

### 4.3 Cortex Search Service Feed
* `V_CORPUS_SEARCH_FEED` prepares the text search payload with document title, doc_type, category, failure_code, machine_type, component_type, and body text.
* Includes DDL declaration for `CORTEX SEARCH SERVICE KNOWLEDGE_SEARCH_SERVICE` with token indexing.

---

## 5. M21 Reliability Evidence Chain (Phase 2G Factual Verification)

The complete cross-domain reliability evidence chain for primary spotlight machine **M21** is factually verified:

```text
[Telemetry Exceedance]
  Machine: M21 (Grinder 3, model GR-600, Line L5)
  Sensor: S-M21-VIB (4.88 mm/s > critical limit 4.50 mm/s)
  Sensor: S-M21-BTMP (84.2 degC elevated temperature)
       ↓
[ML Prediction]
  Prediction ID: PRED-000322 (Scored 2026-09-28 23:00)
  Suspected Component: C-M21-BRG (Drive-End Bearing 6206-2RS)
  Failure Probability: 0.950 (Risk Level: HIGH)
  Top Features: VIB_max (50%), VIB_mean (27%), VIB_rel30 (22%)
       ↓
[Failure Mode Taxonomy]
  Failure Code: BD-BRG ("Bearing Breakdown")
  Primary Sensors: vibration_rms, bearing_temperature
  Action: Replace bearing assembly, inspect housing, regrease & align shaft
       ↓
[Inventory Risk]
  Part: SP-002 ("Drive-End Bearing 6206-2RS")
  Stock: 0 units (STOCKOUT, is_critical_exposure = TRUE)
  Lead Time: 5 days (Supplier: SUP-12 Vertex Industrial Supplies)
       ↓
[Production Impact & Financial Exposure]
  Customer Order: PRD-01278 (Customer: Keystone Hydraulics)
  Due Date: 2026-09-29 (1 day remaining)
  Unfulfilled Units: 211 units (Produced 3,683 of 3,894)
  Revenue at Risk: INR 83,134 (211 units x ₹394)
       ↓
[Knowledge Resolution]
  Documents: DOC-001 (Bearing Troubleshooting SOP), DOC-002 (ISO 10816 Limits),
             DOC-010 (CBM Policy), DOC-011 (Expedited PO Policy for Critical Stockouts)
```

---

## 6. Verification and Test Results

### Test Suite Execution
* Total test cases: **154** (153 passed, 1 skipped).
* Zero regressions on legacy M204 tests.
* Full test coverage across:
  * `tests/data_quality/test_analytics_data_quality.py` (OEE bounds, downtime, inventory exposure, DDL verification).
  * `tests/integration/test_m21_evidence_chain.py` (complete factual M21 chain).
  * `tests/repositories/test_analytics_repositories.py` (contract parity and filtering).

### Syntax and Static Quality
* `python -m compileall .` completed with 0 errors.
* `snowflake/scripts/init_coco_factory.py --dry-run` completed with 83 statements successfully planned across all 10 SQL scripts.

---

## 7. Deferred Items (Out of Milestone 2 Scope)

In strict adherence to `AGENT.md` v2.0 milestone isolation:
1. **CoCo Conversational Agent**: Multi-turn dialog, agent reasoning loop, and LLM orchestration are deferred to Milestone 4.
2. **Autonomous Governance / Work Order Execution**: Automatic work order dispatch, approval workflow UI, and technician push notifications are deferred to Milestone 3 / 4.
3. **Live Snowflake Cortex Search Deployment**: The Cortex Search service SQL DDL is created and verified; live cloud deployment requires active Snowflake credentials in production.
4. **Streamlit UI Redesign**: The UI remains operational and compatible with existing views; modern multi-tab redesign is deferred to Milestone 5.
5. **Live Telemetry Replay Runner**: Replay scripts are staged; live Kafka/Snowpipe streaming is deferred to the streaming phase.
