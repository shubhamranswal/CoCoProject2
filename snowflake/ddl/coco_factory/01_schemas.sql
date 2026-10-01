-- 01_schemas.sql
-- Schema creation for COCO_FACTORY per AGENT.md Milestone 1

USE DATABASE COCO_FACTORY;

CREATE SCHEMA IF NOT EXISTS RAW
    COMMENT = 'Bronze/RAW landing zone for factory telemetry and ERP source files';

CREATE SCHEMA IF NOT EXISTS CORE
    COMMENT = 'Silver/CORE conformed dimensional and relational models with strict constraints';

CREATE SCHEMA IF NOT EXISTS ANALYTICS
    COMMENT = 'Gold/ANALYTICS views and aggregates for reporting, OEE, and operational dashboards';

CREATE SCHEMA IF NOT EXISTS ML
    COMMENT = 'Predictive models, inference logs, feature stores, and degradation scores';

CREATE SCHEMA IF NOT EXISTS KNOWLEDGE
    COMMENT = 'Unstructured manual documents, failure mode taxonomy, and Cortex Search corpus';

CREATE SCHEMA IF NOT EXISTS APP
    COMMENT = 'Application operational state, alert workflows, approval gates, and audit trails';
