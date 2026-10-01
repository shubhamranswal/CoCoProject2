-- 50_knowledge_foundation.sql
-- Milestone 2 Knowledge Foundation: Normalized Corpus, Failure Mode Taxonomy, and Cortex Search Service

USE DATABASE COCO_FACTORY;
USE SCHEMA KNOWLEDGE;

-- 1. Normalized Document Corpus for Semantic Retrieval & Cortex Search (Phase 2C)
CREATE TABLE IF NOT EXISTS CORPUS (
    doc_id                      VARCHAR(32) NOT NULL,
    title                       VARCHAR(256) NOT NULL,
    doc_type                    VARCHAR(64) NOT NULL,
    category                    VARCHAR(64) NOT NULL,
    machine_type                VARCHAR(64),
    component_type              VARCHAR(64),
    failure_code                VARCHAR(32),
    sensor_type                 VARCHAR(64),
    content                     VARCHAR(16777216) NOT NULL,
    token_count                 INT,
    source_file                 VARCHAR(256),
    metadata_json               VARCHAR(4096),
    indexed_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_knowledge_corpus PRIMARY KEY (doc_id)
);

-- 2. Conformed Population of Normalized Knowledge Corpus from CORE
MERGE INTO KNOWLEDGE.CORPUS t
USING (
    SELECT
        doc_id,
        title,
        doc_type,
        CASE
            WHEN doc_type = 'troubleshooting' THEN 'DIAGNOSTICS'
            WHEN doc_type = 'reference' THEN 'ENGINEERING_REFERENCE'
            WHEN doc_type = 'sop' THEN 'OPERATING_PROCEDURE'
            WHEN doc_type = 'policy' THEN 'GOVERNANCE'
            WHEN doc_type = 'oem_manual' THEN 'OEM_MANUAL'
            ELSE 'GENERAL'
        END AS category,
        machine_type,
        component_type,
        CASE
            WHEN component_type = 'Drive-End Bearing' THEN 'BD-BRG'
            WHEN component_type = 'Drive Motor' THEN 'BD-MTR'
            WHEN component_type = 'Hydraulic Pump' THEN 'BD-HYD'
            WHEN component_type = 'Coolant Pump' THEN 'BD-CLT'
            WHEN component_type = 'Gearbox/Drive Belt' THEN 'BD-DRV'
            WHEN component_type = 'PLC/Electrical Panel' THEN 'BD-ELC'
            WHEN component_type = 'Tooling' THEN 'BD-TLG'
            ELSE 'PM-ROUTINE'
        END AS failure_code,
        CASE
            WHEN component_type = 'Drive-End Bearing' THEN 'vibration_rms, bearing_temperature'
            WHEN component_type = 'Drive Motor' THEN 'motor_current, winding_temperature'
            WHEN component_type = 'Hydraulic Pump' THEN 'hydraulic_pressure'
            WHEN component_type = 'Coolant Pump' THEN 'coolant_flow'
            WHEN component_type = 'Gearbox/Drive Belt' THEN 'rotational_speed'
            ELSE 'general'
        END AS sensor_type,
        content,
        ARRAY_SIZE(SPLIT(content, ' ')) AS token_count,
        'knowledge_doc.csv' AS source_file,
        TO_VARCHAR(OBJECT_CONSTRUCT(
            'doc_id', doc_id,
            'title', title,
            'doc_type', doc_type,
            'machine_type', machine_type,
            'component_type', component_type
        )) AS metadata_json
    FROM COCO_FACTORY.CORE.KNOWLEDGE_DOC
) s
ON t.doc_id = s.doc_id
WHEN MATCHED THEN UPDATE SET
    t.title = s.title,
    t.doc_type = s.doc_type,
    t.category = s.category,
    t.machine_type = s.machine_type,
    t.component_type = s.component_type,
    t.failure_code = s.failure_code,
    t.sensor_type = s.sensor_type,
    t.content = s.content,
    t.token_count = s.token_count,
    t.source_file = s.source_file,
    t.metadata_json = s.metadata_json,
    t.indexed_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    doc_id, title, doc_type, category, machine_type, component_type,
    failure_code, sensor_type, content, token_count, source_file, metadata_json
) VALUES (
    s.doc_id, s.title, s.doc_type, s.category, s.machine_type, s.component_type,
    s.failure_code, s.sensor_type, s.content, s.token_count, s.source_file, s.metadata_json
);

-- 3. Deterministic Failure Mode Taxonomy (Phase 2D)
CREATE TABLE IF NOT EXISTS FAILURE_MODE_TAXONOMY (
    failure_code                VARCHAR(32) NOT NULL,
    name                        VARCHAR(128) NOT NULL,
    category                    VARCHAR(64) NOT NULL,
    component_type              VARCHAR(64) NOT NULL,
    symptoms                    VARCHAR(512) NOT NULL,
    related_sensor_types        VARCHAR(128) NOT NULL,
    recommended_diagnostic_checks VARCHAR(512) NOT NULL,
    recommended_action_template VARCHAR(512) NOT NULL,
    standard_labor_hours        FLOAT NOT NULL,
    knowledge_doc_refs          VARCHAR(128) NOT NULL,
    degradation_type            BOOLEAN NOT NULL DEFAULT TRUE,
    created_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_failure_mode_taxonomy PRIMARY KEY (failure_code)
);

-- Seed canonical failure mode taxonomy (Idempotent MERGE for all 10 canonical failure codes)
MERGE INTO KNOWLEDGE.FAILURE_MODE_TAXONOMY t
USING (
    SELECT 'BD-BRG' AS failure_code, 'Bearing Breakdown' AS name, 'MECHANICAL' AS category, 'Drive-End Bearing' AS component_type,
           'Machine tripped on high vibration, bearing knock' AS symptoms,
           'vibration_rms, bearing_temperature' AS related_sensor_types,
           'Measure spectral peak at ball pass frequency, inspect lubricant discoloration' AS recommended_diagnostic_checks,
           'Replace bearing assembly, inspect housing, regrease and align shaft' AS recommended_action_template,
           4.0 AS standard_labor_hours, 'DOC-001, DOC-002, DOC-014' AS knowledge_doc_refs, TRUE AS degradation_type
    UNION ALL
    SELECT 'PD-VIB', 'Predictive Bearing Degradation', 'MECHANICAL', 'Drive-End Bearing',
           'High-frequency vibration RMS escalation above warning limit (2.8 mm/s)',
           'vibration_rms, bearing_temperature',
           'Perform 7-day trend slope analysis, check bearing thermocouple probe temperature',
           'Schedule proactive bearing replacement before catastrophic race spalling',
           3.0, 'DOC-001, DOC-002', TRUE
    UNION ALL
    SELECT 'BD-MTR', 'Motor Winding / Stator Failure', 'ELECTRICAL', 'Drive Motor',
           'Burning odor near motor enclosure, drive fault trip',
           'motor_current, winding_temperature',
           'Megger insulation resistance test, phase balance current measurement',
           'Repair or replace drive motor, clean cooling airway, verify phase balance',
           6.0, 'DOC-003, DOC-015', TRUE
    UNION ALL
    SELECT 'PD-CUR', 'Predictive Motor Current Overload', 'ELECTRICAL', 'Drive Motor',
           'Current draw trending above nominal under steady mechanical load',
           'motor_current',
           'Inspect mechanical coupling binding, motor winding temperature drift',
           'Inspect driven component for binding, lubricate transmission',
           2.5, 'DOC-003', TRUE
    UNION ALL
    SELECT 'BD-HYD', 'Hydraulic Pressure Loss', 'HYDRAULIC', 'Hydraulic Pump',
           'Hydraulic pressure unstable, pump whining noise, slow cylinder stroke',
           'hydraulic_pressure',
           'Inspect proportional valve spool, check accumulator pre-charge and filter pressure drop',
           'Replace worn hydraulic component, flush system oil and change filter cartridge',
           3.5, 'DOC-004, DOC-013', TRUE
    UNION ALL
    SELECT 'BD-CLT', 'Coolant Circulation Failure', 'COOLING', 'Coolant Pump',
           'Coolant flow low warning, pump noisy, chip flushing ineffective',
           'coolant_flow',
           'Inspect suction strainer for swarf blockage, verify pump impeller clearance',
           'Clean suction strainer, replace worn impeller, refill coolant reservoir',
           2.5, 'DOC-005, DOC-014', TRUE
    UNION ALL
    SELECT 'BD-DRV', 'Drive Belt / Gearbox Mechanical Wear', 'MECHANICAL', 'Gearbox/Drive Belt',
           'Gearbox noise, severe backlash, belt squeal upon spindle acceleration',
           'rotational_speed',
           'Check belt tension frequency, measure gearbox output shaft play',
           'Replace drive belt or worn gear set, set tension and verify alignment',
           3.0, 'DOC-006, DOC-016', TRUE
    UNION ALL
    SELECT 'BD-ELC', 'Electrical Panel / PLC Fault', 'ELECTRICAL', 'PLC/Electrical Panel',
           'Control panel emergency stop trip, random 24V bus dip',
           'general',
           'Check 24V power supply ripple, inspect I/O module terminal blocks',
           'Reseat or replace faulty I/O module, tighten terminal screws and test I/O rack',
           2.0, 'DOC-007', FALSE
    UNION ALL
    SELECT 'BD-TLG', 'Tooling Wear & Dimension Drift', 'TOOLING', 'Tooling',
           'Dimension drift traced to cutting insert, surface finish degradation',
           'general',
           'Inspect cutting edge chipping under toolmaker microscope',
           'Change indexable inserts, re-set workpiece reference offsets',
           1.0, 'DOC-008', FALSE
    UNION ALL
    SELECT 'PM-ROUTINE', 'Preventive Maintenance Inspection', 'PREVENTIVE', 'General',
           'Scheduled operating hours interval reached',
           'all',
           'Follow standard PM checklist: lubrication, fastener torque, visual inspection',
           'Execute PM routine inspection checklist and update machine logbook',
           2.0, 'DOC-009, DOC-010', FALSE
) s
ON t.failure_code = s.failure_code
WHEN MATCHED THEN UPDATE SET
    t.name = s.name,
    t.category = s.category,
    t.component_type = s.component_type,
    t.symptoms = s.symptoms,
    t.related_sensor_types = s.related_sensor_types,
    t.recommended_diagnostic_checks = s.recommended_diagnostic_checks,
    t.recommended_action_template = s.recommended_action_template,
    t.standard_labor_hours = s.standard_labor_hours,
    t.knowledge_doc_refs = s.knowledge_doc_refs,
    t.degradation_type = s.degradation_type
WHEN NOT MATCHED THEN INSERT (
    failure_code, name, category, component_type, symptoms, related_sensor_types,
    recommended_diagnostic_checks, recommended_action_template, standard_labor_hours,
    knowledge_doc_refs, degradation_type
) VALUES (
    s.failure_code, s.name, s.category, s.component_type, s.symptoms, s.related_sensor_types,
    s.recommended_diagnostic_checks, s.recommended_action_template, s.standard_labor_hours,
    s.knowledge_doc_refs, s.degradation_type
);

-- 4. Cortex Search Service Definition (Phase 2H)
-- Note: Evaluated during live Snowflake deployment where Cortex Search features are licensed.
-- During dry-run / local mode, syntax is validated as standard declarative service SQL.
CREATE OR REPLACE VIEW V_CORPUS_SEARCH_FEED AS
SELECT
    doc_id,
    title,
    doc_type,
    category,
    machine_type,
    component_type,
    failure_code,
    sensor_type,
    content
FROM COCO_FACTORY.KNOWLEDGE.CORPUS;
