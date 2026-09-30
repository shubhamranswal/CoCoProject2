-- Snowflake Database and Schemas Initialization
-- Following architecture/architecture.md and AGENT.md

-- Schemas for Industrial Reliability Command Center
CREATE SCHEMA IF NOT EXISTS FACTORY_RAW COMMENT = 'Source-aligned raw ingestion layer';
CREATE SCHEMA IF NOT EXISTS FACTORY_CORE COMMENT = 'Canonical physical equipment and organizational hierarchy';
CREATE SCHEMA IF NOT EXISTS FACTORY_TELEMETRY COMMENT = 'OT sensor measurements, feature engineering, baselines, and anomalies';
CREATE SCHEMA IF NOT EXISTS FACTORY_PRODUCTION COMMENT = 'Production runs, schedules, operations, and downtime events';
CREATE SCHEMA IF NOT EXISTS FACTORY_QUALITY COMMENT = 'Quality inspections, measurements, and defect records';
CREATE SCHEMA IF NOT EXISTS FACTORY_MAINTENANCE COMMENT = 'Maintenance history, strategies, tasks, and work orders';
CREATE SCHEMA IF NOT EXISTS FACTORY_RELIABILITY COMMENT = 'Failure events, failure modes, failure risks, and health assessments';
CREATE SCHEMA IF NOT EXISTS FACTORY_KNOWLEDGE COMMENT = 'Engineering manuals, SOPs, and searchable knowledge chunks';
CREATE SCHEMA IF NOT EXISTS FACTORY_INTELLIGENCE COMMENT = 'Active reliability alerts, investigations, evidence, and recommendations';
CREATE SCHEMA IF NOT EXISTS FACTORY_AGENT COMMENT = 'Operational agent state, execution records, approvals, and verification';
CREATE SCHEMA IF NOT EXISTS FACTORY_AUDIT COMMENT = 'Immutable operational audit events and access logs';
