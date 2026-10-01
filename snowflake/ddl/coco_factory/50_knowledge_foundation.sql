-- 50_knowledge_foundation.sql
-- Knowledge schema foundation: Cortex Search readiness and failure mode taxonomy

USE DATABASE COCO_FACTORY;
USE SCHEMA KNOWLEDGE;

-- 1. Unstructured Document Corpus for Cortex Search
CREATE TABLE IF NOT EXISTS CORPUS (
    doc_id                      VARCHAR(32) NOT NULL,
    doc_type                    VARCHAR(64) NOT NULL,
    machine_type                VARCHAR(64),
    component_type              VARCHAR(64),
    title                       VARCHAR(256) NOT NULL,
    content                     VARCHAR(16777216) NOT NULL,
    token_count                 INT,
    indexed_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_knowledge_corpus PRIMARY KEY (doc_id)
);

-- 2. Failure Mode Taxonomy
CREATE TABLE IF NOT EXISTS FAILURE_MODE_TAXONOMY (
    failure_code                VARCHAR(32) NOT NULL,
    name                        VARCHAR(128) NOT NULL,
    category                    VARCHAR(64) NOT NULL,
    affected_component_type     VARCHAR(64) NOT NULL,
    degradation_type            BOOLEAN NOT NULL DEFAULT TRUE,
    recommended_action_template VARCHAR(512),
    standard_labor_hours        FLOAT,
    created_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_failure_mode_taxonomy PRIMARY KEY (failure_code)
);

-- Seed canonical failure mode taxonomy
INSERT INTO FAILURE_MODE_TAXONOMY (failure_code, name, category, affected_component_type, degradation_type, recommended_action_template, standard_labor_hours)
VALUES
    ('BD-BRG', 'Bearing Degradation', 'MECHANICAL', 'Drive-End Bearing', TRUE, 'Inspect and replace degraded bearing assembly', 4.0),
    ('BD-MTR', 'Motor Winding Degradation', 'ELECTRICAL', 'Drive Motor', TRUE, 'Check insulation resistance and rewind/replace motor', 6.0),
    ('BD-HYD', 'Hydraulic Pressure Loss', 'HYDRAULIC', 'Hydraulic Pack', TRUE, 'Check seals, valves, and fluid pressure levels', 3.5),
    ('BD-CLT', 'Coolant System Failure', 'COOLING', 'Coolant Pump', TRUE, 'Flush lines and replace coolant circulation pump', 2.5),
    ('BD-DRV', 'Drive Belt/Gearbox Wear', 'MECHANICAL', 'Gearbox/Drive Belt', TRUE, 'Tension or replace drive belt / inspect gearbox teeth', 3.0);
