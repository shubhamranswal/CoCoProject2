# Milestone 5: Governed Action + Command Center Evolution + Closed-Loop Verification

## 1. Objective & Scope

Milestone 5 achieves the complete closed-loop manufacturing reliability lifecycle for the **Snowflake Factory Reliability / OEE Command Center**. It evolves the read-only CoCo investigation layer (Milestone 4) into an operational, governed execution and closed-loop verification platform:

$$\text{SENSE} \rightarrow \text{UNDERSTAND} \rightarrow \text{PREDICT} \rightarrow \text{INVESTIGATE} \rightarrow \mathbf{\text{RECOMMEND}} \rightarrow \mathbf{\text{APPROVE}} \rightarrow \mathbf{\text{ACT}} \rightarrow \mathbf{\text{VERIFY}} \rightarrow \mathbf{\text{LEARN}}$$

* **Milestone 4 Responsibility:** `PREDICT` $\rightarrow$ `INVESTIGATE` $\rightarrow$ `RECOMMEND` (read-only cross-domain correlation, advisory findings, and recommendations).
* **Milestone 5 Responsibility:** `RECOMMEND` $\rightarrow$ `APPROVE` $\rightarrow$ `ACT` $\rightarrow$ `VERIFY` $\rightarrow$ `LEARN` (action proposals, human-in-the-loop approval gateway, zero-trust action execution, telemetry-based physical verification, and closed-loop learning).

---

## 2. Non-Negotiable Safety & Governance Architecture

Operational actions introduce real-world physical and financial consequences. Milestone 5 enforces zero-trust safety principles across every layer:

1. **Strict Prohibition of Autonomous Consequential Execution:**
   * CoCo and autonomous background agents are strictly barred from directly executing consequential actions (e.g. creating work orders, reserving inventory, assigning staff).
2. **Strict Prohibition of Autonomous Self-Approval:**
   * CoCo cannot approve its own recommendations or proposals.
   * The `ApprovalGateway` validates all approver identities and unconditionally rejects system/agent identities (e.g. `ReliabilityAgent`, `CoCo`, `agent`, `bot`, `orchestrator`, `systemagent`).
3. **Explicit Human Approval Boundary:**
   * Every consequential operational action requires explicit human operator sign-off with recorded authorization reasons and expiration boundaries.
4. **Zero-Trust Execution Pipeline:**
   $$\text{Proposal} \rightarrow \text{Approval Verification} \rightarrow \text{Precondition Check} \rightarrow \text{Idempotency Check} \rightarrow \text{Typed Tool Execution} \rightarrow \text{Audit Logging} \rightarrow \text{Verification} \rightarrow \text{Learning Outcome}$$
5. **Tool Registry Isolation & Action Firewall:**
   * `M4InvestigationToolRegistry` accepts **only** `ToolMode.READ` tools. Registering an action tool raises `ActionFirewallError`.
   * `M5ActionRegistry` accepts **only** `ToolMode.ACTION` tools. Registering a read tool raises `ActionRegistryError`.
6. **Zero Arbitrary SQL / Query Injection:**
   * Database access is strictly typed and parameterized. Prohibited query patterns (`execute_sql`, `run_query`, `raw_sql`, `eval`) are blocked at the registry level.
7. **Strict Inventory Reality (No Fabricated Procurement):**
   * The supply chain repository strictly enforces physical inventory. For `SP-002` (where canonical stock is 0 and lead time is 5 days), reservation attempts safely report shortage and failure without corrupting state or generating negative inventory.
8. **Closed-Loop Learning without Premature Automated Retraining:**
   * System records `ActionOutcome` records (capturing post-maintenance labels, confirmation, downtime avoided, verification status) for future offline retraining without unverified model weight mutation.

---

## 3. Governed Action Catalog & Action Registry

The governed `M5ActionRegistry` manages consequential operational tools behind approval verification:

| Action Tool Name | Tool Mode | Target Domain | Input Schema | Output Schema | Safety Constraints |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `create_work_order` | `ACTION` | Maintenance | `CreateWorkOrderInput` | `WorkOrder` | Requires verified human `approval_id`; verifies machine match; derives stable idempotency key |
| `reserve_spare_part` | `ACTION` | Supply Chain | `ReserveSparePartInput` | `ReserveSparePartResult` | Requires verified `approval_id`; checks stock in `CORE.SPARE_PART`; safely rejects shortage (e.g. `SP-002`) |
| `assign_technician` | `ACTION` | Operations | `AssignTechnicianInput` | `AssignTechnicianResult` | Requires verified `approval_id`; assigns authorized personnel; transitions status to `ASSIGNED` |

---

## 4. Precondition Evaluation Service (`ActionPreconditionService`)

Operational actions must satisfy operational preconditions before execution:

* **Machine Precondition:** Validates machine exists in repository and records current operational state.
* **Component Precondition:** Validates specified component belongs to the target machine (e.g. `C-M21-BRG` on `M21`).
* **Inventory Precondition:** Checks real stock quantity and supplier lead times. If `stock_qty < qty` (e.g. `SP-002` where `stock_qty = 0`, `lead_time_days = 5`), safely reports shortage and blocks execution.
* **Technician Precondition:** Validates technician name or ID against active rosters.
* **Idempotency Precondition:** Checks if an execution with the specified `idempotency_key` has already been recorded.

---

## 5. Human Approval Gateway (`ApprovalGateway`)

The `ApprovalGateway` acts as the human governance gate between advisory recommendations and operational execution:

```
ActionProposal (PROPOSED)
          │
          ▼ submit_proposal()
ActionProposal (PENDING_APPROVAL) + Approval (PENDING)
          │
          ├────────────────────────────────────────┐
          ▼ approve_proposal(approver_id, reason)    ▼ reject_proposal(approver_id, reason)
ActionProposal (APPROVED)                 ActionProposal (REJECTED)
Approval (APPROVED)                       Approval (REJECTED)
```

* **Human Identity Validation:** Rejects calls where `approver_id` matches bot or agent prefixes.
* **Expiration Enforcement:** Rejects approvals past `expires_at` with `ApprovalExpiredError`.
* **Idempotency:** Repeated approvals by the same human return the existing approved record without error.

---

## 6. Action Execution Service (`ActionExecutionService`)

The `ActionExecutionService` orchestrates the zero-trust execution pipeline:

1. **Retrieval & Status Verification:** Checks that the proposal exists and is in `APPROVED` status.
2. **Idempotency Short-Circuit:** If a completed `ActionExecution` with the specified `idempotency_key` already exists, returns the existing record immediately.
3. **Approval Verification:** Verifies linked `Approval` is `APPROVED` and unexpired.
4. **Precondition Validation:** Invokes `ActionPreconditionService`. If preconditions fail (e.g. inventory shortage), marks execution as `FAILED`, updates proposal to `FAILED`, logs `AuditEvent`, and safely aborts.
5. **Typed Tool Invocation:** Invokes corresponding tool from `M5ActionRegistry`.
6. **Persistence & State Transition:** Persists `ActionExecution`, updates proposal to `EXECUTED`, and records governance `AuditEvent`.

---

## 7. Closed-Loop Physical Verification (`VerificationService`)

Verification is measured strictly from post-maintenance physical telemetry, not merely technician work order completion:

$$\text{Work Order Completed} \neq \text{Physical Recovery Verified}$$

### Verification Decision Matrix

| Condition | Verification Verdict | Lifecycle Actions |
| :--- | :--- | :--- |
| **Missing Telemetry** | `INCONCLUSIVE` | Work order remains `COMPLETED` (NOT verified); investigation remains open; outcome logged with `observed_failure_confirmed=False`. |
| **Abnormal Telemetry** (Vib RMS $> 0.50$g, Risk $> 0.25$) | `FAILED` / `VERIFICATION_FAILED` | Work order remains `COMPLETED`; investigation marked `VERIFICATION_FAILED`; outcome logged as failed recovery. |
| **Partial Recovery** (Vib reduction $\ge 20\%$, Risk $\le 0.50$) | `PARTIALLY_VERIFIED` | Investigation marked `REQUIRES_FOLLOW_UP` for continuous monitoring. |
| **Nominal Recovery** (Vib RMS $\le 0.50$g, Temp $\le 65^\circ$C, Risk $\le 0.25$) | `VERIFIED` | Work order advanced to `VERIFIED`; investigation marked `CLOSED`; machine health set to `HEALTHY`. |

---

## 8. Closed-Loop Learning Model (`ActionOutcome`)

Captures post-maintenance verification outcomes as ground truth labels for future predictive model training:

```python
class ActionOutcome(BaseModel):
    outcome_id: str
    action_proposal_id: str
    work_order_id: str
    prediction_id: Optional[str]
    machine_id: str
    failure_mode: str
    observed_failure_confirmed: bool
    downtime_avoided_hours: float
    verification_status: VerificationStatus
    feedback_notes: str
    recorded_at: datetime
```

* **No Automated Model Retraining:** Milestone 5 captures high-fidelity operational labels into `COCO_FACTORY.APP.ACTION_OUTCOME` for governed ML retraining workflows in subsequent releases.

---

## 9. Canonical Flagship Spotlight: M21 (Grinder 3)

The complete closed-loop product loop was validated on canonical asset **M21** (`Grinder 3`):

1. **SENSE & PREDICT:** Canonical prediction `PRED-000322` on `M21` with failure probability $0.95$ and risk `HIGH`.
2. **INVESTIGATE:** CoCo investigation correlates vibration exceedance on sensor `S-M21-VIB` with bearing degradation on component `C-M21-BRG`.
3. **RECOMMEND:** Advisory recommendation generates `ActionProposal` `PROP-M21-001` for bearing replacement and spare part reservation.
4. **APPROVE:** Autonomous self-approval attempts by `ReliabilityAgent` and `CoCo` are rejected with `PermissionError`. Human operator `sarah.chen` approves the replacement proposal.
5. **ACT:**
   * Preconditions check `SP-002` (`Drive-End Bearing 6206-2RS`, compatible model: `6206-2RS`, supplier: `SUP-12`, lead time: 5 days, stock: 0, reorder level: 2, reorder quantity: 4) $\rightarrow$ stockout detected (`stock_qty = 0`, `lead_time_days = 5`); reservation fails safely with honest shortage reporting.
   * Emergency work order is executed idempotently via `create_work_order`.
   * Technician completes physical bearing replacement.
6. **VERIFY:**
   * Missing telemetry test verifies `INCONCLUSIVE` verdict without premature closure.
   * Normalized post-maintenance telemetry (vibration reduced to $0.38$g, temperature $55^\circ$C, risk $0.10$) produces `VERIFIED`.
   * Work order marked `VERIFIED`, investigation marked `CLOSED`, machine marked `HEALTHY`.
7. **LEARN:** `ActionOutcome` record persisted with ground truth label, confirming bearing degradation and recording $12.0$ hours of avoided downtime.

> [!IMPORTANT]
> **Physical-World Truth Boundary & Test Fixture Clarification:**
> In the offline flagship integration test, the post-maintenance telemetry values (vibration $= 0.38$g, temperature $= 55^\circ$C, risk $= 0.10$) and avoided downtime ($12.0$ hours) are **test fixture / simulated post-maintenance inputs** designed to validate the deterministic evaluation logic. They are **not** claims of actual physical maintenance performed on the physical M21 machine.
> 
> The software execution strictly enforces the physical boundary:
> $$\text{CREATE\_WORK\_ORDER} \rightarrow \text{Explicit Technician Completion Event} \rightarrow \text{Pipeline Telemetry Ingestion} \rightarrow \text{Deterministic Verification}$$
> The production verification service evaluates telemetry delivered by the actual OT telemetry ingestion pipeline; the software application never infers physical repair completion merely because a work order was generated, nor does it physically replace components.

---

## 10. Snowflake DDL & Application Foundation

Milestone 5 adds 7 governed operational tables to `COCO_FACTORY.APP` in `snowflake/ddl/coco_factory/60_app_foundation.sql`:

1. `ACTION_PROPOSAL`: Proposals awaiting human governance.
2. `ACTION_APPROVAL`: Human sign-offs and review audit records.
3. `ACTION_EXECUTION`: Consequential tool execution records and results.
4. `ACTION_AUDIT`: Comprehensive compliance and governance audit event log.
5. `VERIFICATION_POLICY`: Deterministic physical recovery thresholds.
6. `VERIFICATION_RESULT`: Before/after physical telemetry evaluation records.
7. `ACTION_OUTCOME`: Ground truth closed-loop learning records.

---

## 11. Verification Gate & Test Results

```bash
python -m pytest
python -m compileall .
python snowflake/scripts/init_coco_factory.py --dry-run
```

* **Test Suite:** **236 passed, 1 skipped** (live Snowflake connectivity test intentionally skipped without live credentials).
* **Compilation:** **0 errors across all repository packages**.
* **Snowflake DDL Validation:** **10 scripts, 99 statements parsed cleanly** in dry run.
* **Regressions:** **0 regressions against Milestones 1–4**.
