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
