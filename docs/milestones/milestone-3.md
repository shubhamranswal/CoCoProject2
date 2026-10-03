# Milestone 3: Predictive Production Layer

## 1. Objective
Establish a production-grade, mathematically deterministic, leakage-free Predictive Production Layer for the Snowflake Factory Reliability Command Center. Milestone 3 implements the **PREDICT** capability within the canonical loop:
$$\text{SENSE} \rightarrow \text{UNDERSTAND} \rightarrow \mathbf{\text{PREDICT}} \rightarrow \text{INVESTIGATE} \rightarrow \text{RECOMMEND} \rightarrow \text{APPROVE} \rightarrow \text{ACT} \rightarrow \text{VERIFY} \rightarrow \text{LEARN}$$

This milestone provides the auditable predictive signals and provenance required by Milestone 4 (CoCo Investigation) and Milestone 5 (Governed Action).

---

## 2. Architecture & Provenance Chain
Predictions are treated as first-class, immutable product entities with complete end-to-end lineage:

```
[Raw OT Telemetry / Hourly Aggregates]
               │
               ▼
[Feature Engineering: Warning Normalization, Rolling Windows]
               │
               ▼
[Prediction Feature Snapshot: ML.PREDICTION_FEATURE_SNAPSHOT]
               │
               ▼
[Model Registry Active Version: HistGradientBoostingClassifier]
               │
               ▼
[Deterministic Inference: Failure Probability (0.0 .. 1.0)]
               │
               ▼
[Risk Policy Classification: Low, Medium, High, Critical]
               │
               ▼
[Prediction Lineage Recording: ML.PREDICTION_LINEAGE]
               │
               ▼
[Core Prediction Fact: CORE.PREDICTION / ML_PREDICTION]
```

Every production prediction is traceable to:
* Target machine and timestamp
* Active model version and algorithm parameters
* Immutable feature snapshot and source window
* Calibrated failure probability and deterministic risk level
* Suspected component and failure mode code
* Top-3 contributing features with proportional attribution shares

---

## 3. Canonical 29-Feature Schema
The model uses 29 canonical features derived from normalized hourly sensor readings and maintenance history:

| Sensor Code | Semantic Metric | Shorthand | Derived Features |
| :--- | :--- | :--- | :--- |
| `vibration_rms` | Drive/Spindle Vibration RMS | `VIB` | `mean`, `max`, `slope7`, `rel30` |
| `bearing_temperature` | Bearing Operating Temp | `BTMP` | `mean`, `max`, `slope7`, `rel30` |
| `motor_current` | Drive Motor Current | `CUR` | `mean`, `max`, `slope7`, `rel30` |
| `winding_temperature` | Stator Winding Temp | `WTMP` | `mean`, `max`, `slope7`, `rel30` |
| `rotational_speed` | Shaft Rotational Speed | `RPM` | `mean`, `max`, `slope7`, `rel30` |
| `hydraulic_pressure` | System Hydraulic Pressure | `PRS` | `mean`, `max`, `slope7`, `rel30` |
| `coolant_flow` | Coolant Circuit Flow | `FLW` | `mean`, `max`, `slope7`, `rel30` |
| Maintenance | Maintenance Recency | - | `days_since_maint` |

### Normalization & Transformation Rules
1. **Warning Normalization**: $x_{\text{norm}} = \frac{x}{\text{warn\_threshold}}$ ($1.0$ represents operating at warning limit). For inverted metrics (e.g. pressure drop), $x_{\text{norm}} = \frac{\text{warn\_threshold}}{x}$.
2. **7-Day Slope (`slope7`)**: 1st-degree polynomial fit over active 7-day rolling window ($\ge 3$ valid points required).
3. **30-Day Relative Baseline (`rel30`)**: $\frac{\text{mean}_i}{\text{median}(\text{mean}_{i-30..i-7})}$.
4. **Maintenance Recency (`days_since_maint`)**: $\min(\text{days elapsed since last closed maintenance order}, 120.0)$.

---

## 4. Target Definition
* **Horizon**: $168\text{ hours}$ (7 calendar days).
* **Qualifying Failure Codes**:
  * `BD-BRG`: Bearing degradation and mechanical spalling
  * `BD-MTR`: Motor overheating / insulation degradation
  * `BD-HYD`: Hydraulic pressure loss and seal rupture
  * `BD-CLT`: Coolant flow restriction / thermal runaway
  * `BD-DRV`: Drive misalignment and mechanical binding
* **Label Rule**: $\text{Target} = 1$ if a qualifying corrective maintenance work order starts within $(T, T + 7\text{ days}]$, else $0$.

---

## 5. Temporal Leakage Controls
To guarantee zero future leakage:
* **Sensor Windows**: A feature computed at $T$ only consumes telemetry timestamps $\le T$.
* **Maintenance Boundary**: `days_since_maint` only filters closed work orders where $\text{DATE}(w.\text{closed\_ts}) \le \text{feature\_date}$. Future maintenance is strictly excluded.
* **Split Buffer**: A mandatory 7-day gap between training period end and test period start prevents target horizon overlap.

---

## 6. Chronological Train / Test Split
Random shuffling is strictly prohibited. The canonical historical timeline (12 months) is partitioned chronologically:
* **Test Window**: Most recent $85\text{ days}$ of history.
* **Separation Buffer**: $7\text{ days}$ (matching prediction horizon).
* **Training Window**: All history strictly prior to $\text{test\_start} - 7\text{ days}$.

---

## 7. Model Configuration
* **Algorithm**: `HistGradientBoostingClassifier`
* **Hyperparameters**:
  * `max_iter = 200`
  * `learning_rate = 0.06`
  * `max_depth = 4`
  * `l2_regularization = 1.0`
  * `random_state = 0` (strictly deterministic)
* **Sample Weighting**: $3.0\times$ weight on positive failure instances to counteract class imbalance.

---

## 8. Evaluation Metrics
* **Discrimination**: ROC-AUC, PR-AUC
* **Operational Performance**: Precision @ 0.50, Recall @ 0.50, F1 Score
* **Diagnostic Verification**: Confusion Matrix ($\text{TP}, \text{FP}, \text{TN}, \text{FN}$)
* **Calibration**: Output probabilities represent monotonic failure likelihoods.

---

## 9. Deterministic Risk Policy
Operational risk tiering is governed by `RiskPolicy` (version `v1.0-canonical-thresholds`):
* **$\ge 0.85$**: `CRITICAL` (Immediate intervention required)
* **$\ge 0.70$**: `HIGH` / `"high"`
* **$0.40 \le P < 0.70$**: `MEDIUM` / `"medium"`
* **$< 0.40$**: `LOW` / `"low"`

No LLM or stochastic model is permitted in probability scoring or risk tier assignment.

---

## 10. Model Registry Architecture
Registered in `COCO_FACTORY.ML.MODEL_REGISTRY`:
* `model_id`, `model_name`, `model_version`, `algorithm`
* `training_dataset_version`, `feature_version`, `target_definition`
* `training_start_date`, `training_end_date`, `test_start_date`, `test_end_date`
* `auc_roc`, `pr_auc`, `precision_at_threshold`, `recall_at_threshold`, `f1_score`
* `artifact_location`, `artifact_checksum` (SHA-256)
* `status` (`candidate`, `validated`, `active`, `retired`)

---

## 11. Feature Snapshot Design
Stored in `COCO_FACTORY.ML.PREDICTION_FEATURE_SNAPSHOT`:
* `snapshot_id`: `SNAP-{machine_id}-{timestamp}`
* `prediction_id`: `PRED-{machine_id}-{timestamp}`
* `features_json`: Exact 29-feature vector at time of scoring
* `source_window_start`, `source_window_end`

---

## 12. Prediction Lineage
Recorded in `COCO_FACTORY.ML.PREDICTION_LINEAGE`:
* Connects `prediction_id` $\leftrightarrow$ `model_version` $\leftrightarrow$ `snapshot_id`
* Captures `inference_timestamp`, `failure_probability`, `risk_level`, and `policy_version`.

---

## 13. Idempotent Inference
Inference enforces strict idempotency on the natural key:
$$\text{Natural Key} = (\text{machine\_id}, \text{prediction\_timestamp}, \text{model\_version}, \text{feature\_version})$$
Repeated runs return the existing record and create zero duplicate database rows.

---

## 14. Canonical M21 Verification
* **Canonical Historical Record**: `PRED-000322` on `M21` ($0.95$ prob, `C-M21-BRG`, `BD-BRG`, `VIB_max 0.50`, `VIB_mean 0.27`, `VIB_rel30 0.22`) is preserved.
* **New Production Inference**: Identifies the same underlying physical failure pattern on `M21`:
  * Evaluates severe vibration exceedances ($4.881\text{ mm/s}$ vs $2.8$ warn / $4.5$ crit) and bearing temperature ($84.55^\circ\text{C}$ vs $75^\circ\text{C}$ warn).
  * Automatically resolves suspected component `C-M21-BRG` and failure code `BD-BRG`.
  * Flags `CRITICAL` / `high` risk with `VIB_max`, `VIB_mean`, `VIB_rel30` as top contributors.

---

## 15. Snowflake DDL Extensions
Script: [snowflake/ddl/coco_factory/40_ml_foundation.sql](file:///c:/Users/shubh/Desktop/coco/snowflake/ddl/coco_factory/40_ml_foundation.sql)
1. `COCO_FACTORY.ML.MODEL_REGISTRY` (Expanded with lifecycle status, periods, checksum)
2. `COCO_FACTORY.ML.MACHINE_FEATURE_DAILY` (Feature store table)
3. `COCO_FACTORY.ML.V_MACHINE_FEATURE_DAILY` (Leakage-free view)
4. `COCO_FACTORY.ML.INFERENCE_LOG` (Execution audit log)
5. `COCO_FACTORY.ML.MODEL_EVALUATION` (Chronological split metrics)
6. `COCO_FACTORY.ML.PREDICTION_FEATURE_SNAPSHOT` (Immutable feature payloads)
7. `COCO_FACTORY.ML.PREDICTION_LINEAGE` (Auditable prediction provenance)

---

## 16. Verification Classification
* **Local Offline Environment**: **PASS** (174 legacy tests + 11 new Milestone 3 ML/lineage/acceptance tests passing).
* **Live Snowflake Deployment**: **PENDING CREDENTIALS** (Dry-run parser validated 10 scripts and 86 statements; live execution requires active Snowflake account credentials).

---

## 17. Milestone 4 Interface Readiness
The following interfaces are now available for CoCo in Milestone 4:
* `prediction_service.generate_prediction()`: Generates auditable predictions.
* `ml_repository.get_prediction_lineage(pred_id)`: Traces provenance back to model and feature snapshot.
* `ml_repository.get_prediction_feature_snapshot(snapshot_id)`: Supplies exact feature attribution.
* `ml_repository.get_active_model()`: Validates model version integrity.
