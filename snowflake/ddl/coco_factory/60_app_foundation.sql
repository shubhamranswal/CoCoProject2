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
