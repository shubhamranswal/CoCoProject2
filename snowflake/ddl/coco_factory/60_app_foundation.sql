-- 60_app_foundation.sql
-- Application Operational State, Governed Workflows, and Agent Audit Trails

USE DATABASE COCO_FACTORY;
USE SCHEMA APP;

-- 1. Alert Workflow State
CREATE TABLE IF NOT EXISTS ALERT_WORKFLOW (
    workflow_id                 VARCHAR(64) NOT NULL,
    alert_id                    VARCHAR(32) NOT NULL,
    machine_id                  VARCHAR(32) NOT NULL,
    status                      VARCHAR(32) NOT NULL,
    investigation_id            VARCHAR(64),
    recommendation_id           VARCHAR(64),
    approval_id                 VARCHAR(64),
    work_order_id               VARCHAR(32),
    created_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    updated_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_app_alert_workflow PRIMARY KEY (workflow_id)
);

-- 2. Human Approval Gate Log
CREATE TABLE IF NOT EXISTS APPROVAL_AUDIT (
    approval_id                 VARCHAR(64) NOT NULL,
    investigation_id            VARCHAR(64) NOT NULL,
    machine_id                  VARCHAR(32) NOT NULL,
    recommended_action          VARCHAR(512) NOT NULL,
    approved_by                 VARCHAR(128) NOT NULL,
    approved_at                 TIMESTAMP_NTZ NOT NULL,
    status                      VARCHAR(32) NOT NULL,
    rejection_reason            VARCHAR(512),
    work_order_id               VARCHAR(32),
    created_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_app_approval_audit PRIMARY KEY (approval_id)
);

-- 3. Agent Execution Audit Trail
CREATE TABLE IF NOT EXISTS AGENT_AUDIT (
    audit_id                    VARCHAR(64) NOT NULL,
    session_id                  VARCHAR(64) NOT NULL,
    agent_name                  VARCHAR(64) NOT NULL,
    action_type                 VARCHAR(64) NOT NULL,
    tool_name                   VARCHAR(64),
    tool_inputs                 VARCHAR(4096),
    tool_outputs                VARCHAR(16777216),
    safety_verdict              VARCHAR(32) NOT NULL DEFAULT 'ALLOWED',
    latency_ms                  FLOAT,
    executed_at                 TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_app_agent_audit PRIMARY KEY (audit_id)
);

-- 4. Investigation Master Record
CREATE TABLE IF NOT EXISTS INVESTIGATION (
    investigation_id            VARCHAR(64) NOT NULL,
    trigger_type                VARCHAR(32) NOT NULL,
    trigger_id                  VARCHAR(64),
    prediction_id               VARCHAR(64),
    alert_id                    VARCHAR(64),
    machine_id                  VARCHAR(32) NOT NULL,
    component_id                VARCHAR(64),
    scope                       VARCHAR(64) DEFAULT 'EQUIPMENT_RELIABILITY',
    status                      VARCHAR(32) NOT NULL,
    failure_mode                VARCHAR(64),
    confidence                  FLOAT,
    summary                     VARCHAR(4096),
    limitations                 VARIANT,
    provenance                  VARIANT,
    started_at                  TIMESTAMP_NTZ,
    completed_at                TIMESTAMP_NTZ,
    created_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_app_investigation PRIMARY KEY (investigation_id)
);

-- 5. Investigation Evidence Store
CREATE TABLE IF NOT EXISTS INVESTIGATION_EVIDENCE (
    evidence_id                 VARCHAR(64) NOT NULL,
    investigation_id            VARCHAR(64) NOT NULL,
    evidence_type               VARCHAR(64) NOT NULL,
    category                    VARCHAR(64) NOT NULL,
    source                      VARCHAR(128),
    source_type                 VARCHAR(64),
    source_id                   VARCHAR(64),
    metric                      VARCHAR(64),
    observed_value              VARCHAR(512),
    unit                        VARCHAR(32),
    severity                    VARCHAR(32),
    relationship                VARCHAR(32) DEFAULT 'SUPPORTS',
    machine_id                  VARCHAR(32),
    component_id                VARCHAR(64),
    claim                       VARCHAR(2048),
    summary                     VARCHAR(2048),
    source_reference            VARCHAR(256),
    collected_at                TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_app_investigation_evidence PRIMARY KEY (evidence_id),
    CONSTRAINT fk_evidence_investigation FOREIGN KEY (investigation_id) REFERENCES APP.INVESTIGATION (investigation_id)
);

-- 6. Investigation Hypotheses Log
CREATE TABLE IF NOT EXISTS INVESTIGATION_HYPOTHESIS (
    hypothesis_id               VARCHAR(64) NOT NULL,
    investigation_id            VARCHAR(64) NOT NULL,
    hypothesis_name             VARCHAR(256) NOT NULL,
    statement                   VARCHAR(2048),
    failure_mode                VARCHAR(64),
    confidence                  FLOAT,
    status                      VARCHAR(32) NOT NULL,
    rationale                   VARCHAR(2048),
    supporting_evidence_ids     VARIANT,
    contradicting_evidence_ids  VARIANT,
    created_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_app_investigation_hypothesis PRIMARY KEY (hypothesis_id),
    CONSTRAINT fk_hypothesis_investigation FOREIGN KEY (investigation_id) REFERENCES APP.INVESTIGATION (investigation_id)
);

-- 7. Investigation Findings Log
CREATE TABLE IF NOT EXISTS INVESTIGATION_FINDING (
    finding_id                  VARCHAR(64) NOT NULL,
    investigation_id            VARCHAR(64) NOT NULL,
    summary                     VARCHAR(2048) NOT NULL,
    statement                   VARCHAR(2048),
    failure_mode                VARCHAR(64),
    confidence                  FLOAT,
    evidence_refs               VARIANT,
    observed_facts              VARIANT,
    inferences                  VARIANT,
    created_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_app_investigation_finding PRIMARY KEY (finding_id),
    CONSTRAINT fk_finding_investigation FOREIGN KEY (investigation_id) REFERENCES APP.INVESTIGATION (investigation_id)
);

-- 8. Governed Advisory Recommendations (M4 strictly advisory)
CREATE TABLE IF NOT EXISTS INVESTIGATION_RECOMMENDATION (
    recommendation_id           VARCHAR(64) NOT NULL,
    investigation_id            VARCHAR(64) NOT NULL,
    title                       VARCHAR(256) NOT NULL,
    statement                   VARCHAR(2048),
    action_type                 VARCHAR(64) NOT NULL,
    priority                    VARCHAR(32) NOT NULL,
    rationale                   VARCHAR(2048),
    suggested_next_step         VARCHAR(1024),
    action_required             BOOLEAN DEFAULT TRUE,
    status                      VARCHAR(32) NOT NULL DEFAULT 'ADVISORY',
    estimated_downtime_hours    FLOAT,
    suggested_parts             VARIANT,
    suggested_checklist         VARIANT,
    evidence_refs               VARIANT,
    created_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_app_investigation_recommendation PRIMARY KEY (recommendation_id),
    CONSTRAINT fk_recommendation_investigation FOREIGN KEY (investigation_id) REFERENCES APP.INVESTIGATION (investigation_id)
);

-- 9. Investigation Tool Execution Audit Log
CREATE TABLE IF NOT EXISTS INVESTIGATION_TOOL_CALL (
    call_id                     VARCHAR(64) NOT NULL,
    investigation_id            VARCHAR(64) NOT NULL,
    tool_name                   VARCHAR(64) NOT NULL,
    tool_mode                   VARCHAR(32) NOT NULL DEFAULT 'READ',
    scope                       VARCHAR(64),
    parameters                  VARCHAR(4096),
    record_count                INT DEFAULT 0,
    duration_ms                 FLOAT,
    success                     BOOLEAN DEFAULT TRUE,
    error_message               VARCHAR(2048),
    called_at                   TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_app_investigation_tool_call PRIMARY KEY (call_id),
    CONSTRAINT fk_tool_call_investigation FOREIGN KEY (investigation_id) REFERENCES APP.INVESTIGATION (investigation_id)
);

-- 10. Governed Action Proposals (M5 Action Pipeline)
CREATE TABLE IF NOT EXISTS ACTION_PROPOSAL (
    action_proposal_id          VARCHAR(64) NOT NULL,
    investigation_id            VARCHAR(64) NOT NULL,
    recommendation_id           VARCHAR(64) NOT NULL,
    machine_id                  VARCHAR(32) NOT NULL,
    component_id                VARCHAR(64),
    action_type                 VARCHAR(64) NOT NULL,
    priority                    VARCHAR(32) NOT NULL DEFAULT 'HIGH',
    risk_level                  VARCHAR(32) NOT NULL DEFAULT 'HIGH',
    reason                      VARCHAR(2048) NOT NULL,
    parameters                  VARCHAR(4096),
    status                      VARCHAR(32) NOT NULL DEFAULT 'PROPOSED',
    idempotency_key             VARCHAR(128),
    approval_id                 VARCHAR(64),
    requires_approval           BOOLEAN DEFAULT TRUE,
    created_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    updated_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_app_action_proposal PRIMARY KEY (action_proposal_id),
    CONSTRAINT fk_proposal_investigation FOREIGN KEY (investigation_id) REFERENCES APP.INVESTIGATION (investigation_id)
);

-- 11. Human Approval Audit & Gateway Records
CREATE TABLE IF NOT EXISTS ACTION_APPROVAL (
    approval_id                 VARCHAR(64) NOT NULL,
    action_proposal_id          VARCHAR(64),
    investigation_id            VARCHAR(64) NOT NULL,
    machine_id                  VARCHAR(32) NOT NULL,
    requested_action            VARCHAR(64) NOT NULL,
    status                      VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    requested_by                VARCHAR(128) NOT NULL,
    decision_by                 VARCHAR(128),
    decision_at                 TIMESTAMP_NTZ,
    decision_reason             VARCHAR(1024),
    authorization_context       VARCHAR(2048),
    expires_at                  TIMESTAMP_NTZ,
    created_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_app_action_approval PRIMARY KEY (approval_id)
);

-- 12. Governed Action Execution Log
CREATE TABLE IF NOT EXISTS ACTION_EXECUTION (
    execution_id                VARCHAR(64) NOT NULL,
    action_proposal_id          VARCHAR(64) NOT NULL,
    approval_id                 VARCHAR(64) NOT NULL,
    action_type                 VARCHAR(64) NOT NULL,
    machine_id                  VARCHAR(32) NOT NULL,
    executed_by                 VARCHAR(128) NOT NULL,
    status                      VARCHAR(32) NOT NULL DEFAULT 'SUCCESS',
    idempotency_key             VARCHAR(128),
    result_data                 VARCHAR(8192),
    error_message               VARCHAR(2048),
    started_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    completed_at                TIMESTAMP_NTZ,
    CONSTRAINT pk_app_action_execution PRIMARY KEY (execution_id),
    CONSTRAINT fk_execution_proposal FOREIGN KEY (action_proposal_id) REFERENCES APP.ACTION_PROPOSAL (action_proposal_id)
);

-- 13. Governed Action Security & Mutation Audit Trail
CREATE TABLE IF NOT EXISTS ACTION_AUDIT (
    audit_id                    VARCHAR(64) NOT NULL,
    actor                       VARCHAR(128) NOT NULL,
    action_type                 VARCHAR(64) NOT NULL,
    resource_id                 VARCHAR(64) NOT NULL,
    resource_type               VARCHAR(64) NOT NULL,
    status                      VARCHAR(32) NOT NULL DEFAULT 'SUCCESS',
    details                     VARCHAR(4096),
    timestamp                   TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_app_action_audit PRIMARY KEY (audit_id)
);

-- 14. Post-Maintenance Verification Policies
CREATE TABLE IF NOT EXISTS VERIFICATION_POLICY (
    policy_id                   VARCHAR(64) NOT NULL,
    machine_id                  VARCHAR(32),
    failure_mode                VARCHAR(64),
    max_acceptable_vibration_rms FLOAT DEFAULT 0.50,
    max_acceptable_temperature  FLOAT DEFAULT 65.0,
    max_acceptable_risk_score   FLOAT DEFAULT 0.25,
    min_vibration_reduction_pct FLOAT DEFAULT 30.0,
    min_risk_reduction_pct      FLOAT DEFAULT 50.0,
    baseline_window_hours       INT DEFAULT 24,
    verification_window_hours   INT DEFAULT 24,
    created_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_app_verification_policy PRIMARY KEY (policy_id)
);

-- 15. Closed-Loop Telemetry Verification Results
CREATE TABLE IF NOT EXISTS VERIFICATION_RESULT (
    verification_id             VARCHAR(64) NOT NULL,
    investigation_id            VARCHAR(64) NOT NULL,
    work_order_id               VARCHAR(32) NOT NULL,
    machine_id                  VARCHAR(32) NOT NULL,
    action_execution_id         VARCHAR(64),
    status                      VARCHAR(32) NOT NULL,
    pre_vibration_rms           FLOAT,
    post_vibration_rms          FLOAT,
    pre_temperature_c           FLOAT,
    post_temperature_c          FLOAT,
    pre_risk_score              FLOAT,
    post_risk_score             FLOAT,
    risk_delta                  FLOAT DEFAULT 0.0,
    is_recovered                BOOLEAN DEFAULT FALSE,
    verification_reason         VARCHAR(2048),
    evaluated_by                VARCHAR(128) DEFAULT 'SYSTEM',
    verified_at                 TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_app_verification_result PRIMARY KEY (verification_id)
);

-- 16. Closed-Loop Learning Outcomes (Historical Label Generation)
CREATE TABLE IF NOT EXISTS ACTION_OUTCOME (
    outcome_id                  VARCHAR(64) NOT NULL,
    action_proposal_id          VARCHAR(64) NOT NULL,
    execution_id                VARCHAR(64),
    verification_id             VARCHAR(64),
    work_order_id               VARCHAR(32) NOT NULL,
    prediction_id               VARCHAR(64),
    machine_id                  VARCHAR(32) NOT NULL,
    failure_mode                VARCHAR(64) NOT NULL,
    observed_failure_confirmed  BOOLEAN DEFAULT TRUE,
    downtime_avoided_hours      FLOAT DEFAULT 0.0,
    verification_status         VARCHAR(32) NOT NULL,
    telemetry_provenance        VARIANT,
    is_simulated_telemetry      BOOLEAN DEFAULT FALSE,
    feedback_notes              VARCHAR(2048),
    recorded_at                 TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_app_action_outcome PRIMARY KEY (outcome_id)
);

