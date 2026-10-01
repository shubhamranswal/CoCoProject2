-- 70_raw_ingestion_copy.sql
-- Idempotent COPY INTO commands for all 19 canonical entities from FACTORY_STAGE into RAW schema
-- Lineage: _BATCH_ID is dynamically injected per execution by init_coco_factory.py.

USE DATABASE COCO_FACTORY;
USE SCHEMA RAW;

-- 1. Machine
COPY INTO RAW.MACHINE (
    machine_id, machine_name, machine_type, model, plant_id, line_id,
    purchase_date, install_date, expected_life_years, expected_end_of_life_date,
    criticality, ideal_cycle_time_sec, rated_power_kw, shifts_per_day, pm_interval_days,
    _source_file, _loaded_at, _batch_id
)
FROM (
    SELECT $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15,
           METADATA$FILENAME, CURRENT_TIMESTAMP(), '__BATCH_ID__'
    FROM @COCO_FACTORY.RAW.FACTORY_STAGE
)
PATTERN = '.*machine\\.csv.*'
FILE_FORMAT = (FORMAT_NAME = CSV_CANONICAL)
ON_ERROR = 'CONTINUE';

-- 2. Component
COPY INTO RAW.COMPONENT (
    component_id, machine_id, component_type, model, purchase_date,
    install_date, expected_life_hrs, operating_hours_used, projected_end_of_life_date,
    _source_file, _loaded_at, _batch_id
)
FROM (
    SELECT $1, $2, $3, $4, $5, $6, $7, $8, $9,
           METADATA$FILENAME, CURRENT_TIMESTAMP(), '__BATCH_ID__'
    FROM @COCO_FACTORY.RAW.FACTORY_STAGE
)
PATTERN = '.*component\\.csv.*'
FILE_FORMAT = (FORMAT_NAME = CSV_CANONICAL)
ON_ERROR = 'CONTINUE';

-- 3. Sensor
COPY INTO RAW.SENSOR (
    sensor_id, machine_id, component_id, sensor_type, unit,
    sampling_rate_hz, warn_threshold, crit_threshold, threshold_direction,
    _source_file, _loaded_at, _batch_id
)
FROM (
    SELECT $1, $2, $3, $4, $5, $6, $7, $8, $9,
           METADATA$FILENAME, CURRENT_TIMESTAMP(), '__BATCH_ID__'
    FROM @COCO_FACTORY.RAW.FACTORY_STAGE
)
PATTERN = '.*sensor\\.csv.*'
FILE_FORMAT = (FORMAT_NAME = CSV_CANONICAL)
ON_ERROR = 'CONTINUE';

-- 4. Sensor Reading (1-minute telemetry)
COPY INTO RAW.SENSOR_READING (
    sensor_id, ts, value,
    _source_file, _loaded_at, _batch_id
)
FROM (
    SELECT $1, $2, $3,
           METADATA$FILENAME, CURRENT_TIMESTAMP(), '__BATCH_ID__'
    FROM @COCO_FACTORY.RAW.FACTORY_STAGE
)
PATTERN = '.*sensor_reading\\.csv.*'
FILE_FORMAT = (FORMAT_NAME = CSV_CANONICAL)
ON_ERROR = 'CONTINUE';

-- 5. Sensor Reading Hourly
COPY INTO RAW.SENSOR_READING_HOURLY (
    sensor_id, ts, run_fraction, avg_running, min_running, max_running,
    _source_file, _loaded_at, _batch_id
)
FROM (
    SELECT $1, $2, $3, $4, $5, $6,
           METADATA$FILENAME, CURRENT_TIMESTAMP(), '__BATCH_ID__'
    FROM @COCO_FACTORY.RAW.FACTORY_STAGE
)
PATTERN = '.*sensor_reading_hourly\\.csv.*'
FILE_FORMAT = (FORMAT_NAME = CSV_CANONICAL)
ON_ERROR = 'CONTINUE';

-- 6. Production Order
COPY INTO RAW.PRODUCTION_ORDER (
    production_order_id, machine_id, product_id, customer, planned_qty,
    produced_qty, planned_start, planned_end, due_date, priority, status,
    _source_file, _loaded_at, _batch_id
)
FROM (
    SELECT $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
           METADATA$FILENAME, CURRENT_TIMESTAMP(), '__BATCH_ID__'
    FROM @COCO_FACTORY.RAW.FACTORY_STAGE
)
PATTERN = '.*production_order\\.csv.*'
FILE_FORMAT = (FORMAT_NAME = CSV_CANONICAL)
ON_ERROR = 'CONTINUE';

-- 7. Production Run
COPY INTO RAW.PRODUCTION_RUN (
    run_id, machine_id, product_id, production_order_id, shift_id, shift_date,
    start_ts, end_ts, planned_time_min, planned_maintenance_min,
    unplanned_downtime_min, run_time_min, ideal_cycle_time_sec, total_count,
    good_count, reject_count,
    _source_file, _loaded_at, _batch_id
)
FROM (
    SELECT $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16,
           METADATA$FILENAME, CURRENT_TIMESTAMP(), '__BATCH_ID__'
    FROM @COCO_FACTORY.RAW.FACTORY_STAGE
)
PATTERN = '.*production_run\\.csv.*'
FILE_FORMAT = (FORMAT_NAME = CSV_CANONICAL)
ON_ERROR = 'CONTINUE';

-- 8. Downtime Event
COPY INTO RAW.DOWNTIME_EVENT (
    event_id, machine_id, run_id, reason_code, category,
    reason_description, start_ts, end_ts, duration_min, wo_id, notes,
    _source_file, _loaded_at, _batch_id
)
FROM (
    SELECT $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
           METADATA$FILENAME, CURRENT_TIMESTAMP(), '__BATCH_ID__'
    FROM @COCO_FACTORY.RAW.FACTORY_STAGE
)
PATTERN = '.*downtime_event\\.csv.*'
FILE_FORMAT = (FORMAT_NAME = CSV_CANONICAL)
ON_ERROR = 'CONTINUE';

-- 9. Maintenance Work Order
COPY INTO RAW.MAINTENANCE_WORK_ORDER (
    wo_id, machine_id, component_id, wo_type, source, priority, failure_code,
    status, scheduled_date, opened_ts, started_ts, closed_ts, assigned_to,
    technicians, labor_hours, parts_cost, labor_cost, cost, prediction_id,
    _source_file, _loaded_at, _batch_id
)
FROM (
    SELECT $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19,
           METADATA$FILENAME, CURRENT_TIMESTAMP(), '__BATCH_ID__'
    FROM @COCO_FACTORY.RAW.FACTORY_STAGE
)
PATTERN = '.*maintenance_work_order\\.csv.*'
FILE_FORMAT = (FORMAT_NAME = CSV_CANONICAL)
ON_ERROR = 'CONTINUE';

-- 10. Technician
COPY INTO RAW.TECHNICIAN (
    technician_id, name, skill_area, shift, hourly_rate_inr,
    _source_file, _loaded_at, _batch_id
)
FROM (
    SELECT $1, $2, $3, $4, $5,
           METADATA$FILENAME, CURRENT_TIMESTAMP(), '__BATCH_ID__'
    FROM @COCO_FACTORY.RAW.FACTORY_STAGE
)
PATTERN = '.*technician\\.csv.*'
FILE_FORMAT = (FORMAT_NAME = CSV_CANONICAL)
ON_ERROR = 'CONTINUE';

-- 11. Maintenance Log
COPY INTO RAW.MAINTENANCE_LOG (
    log_id, wo_id, machine_id, component_id, technician_id, log_ts, wo_type,
    failure_code, root_cause_category, fault_class, symptom, action_taken,
    downtime_min, early_warning_hours, note_text,
    _source_file, _loaded_at, _batch_id
)
FROM (
    SELECT $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15,
           METADATA$FILENAME, CURRENT_TIMESTAMP(), '__BATCH_ID__'
    FROM @COCO_FACTORY.RAW.FACTORY_STAGE
)
PATTERN = '.*maintenance_log\\.csv.*'
FILE_FORMAT = (FORMAT_NAME = CSV_CANONICAL)
ON_ERROR = 'CONTINUE';

-- 12. Work Order Part Usage
COPY INTO RAW.WO_PART_USAGE (
    wo_id, part_id, qty, unit_cost_inr, line_cost_inr,
    _source_file, _loaded_at, _batch_id
)
FROM (
    SELECT $1, $2, $3, $4, $5,
           METADATA$FILENAME, CURRENT_TIMESTAMP(), '__BATCH_ID__'
    FROM @COCO_FACTORY.RAW.FACTORY_STAGE
)
PATTERN = '.*wo_part_usage\\.csv.*'
FILE_FORMAT = (FORMAT_NAME = CSV_CANONICAL)
ON_ERROR = 'CONTINUE';

-- 13. Spare Part
COPY INTO RAW.SPARE_PART (
    part_id, part_name, part_category, compatible_model, unit_cost_inr,
    supplier_id, lead_time_days, stock_qty, reorder_level, reorder_qty, warehouse_bin,
    _source_file, _loaded_at, _batch_id
)
FROM (
    SELECT $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
           METADATA$FILENAME, CURRENT_TIMESTAMP(), '__BATCH_ID__'
    FROM @COCO_FACTORY.RAW.FACTORY_STAGE
)
PATTERN = '.*spare_part\\.csv.*'
FILE_FORMAT = (FORMAT_NAME = CSV_CANONICAL)
ON_ERROR = 'CONTINUE';

-- 14. Supplier
COPY INTO RAW.SUPPLIER (
    supplier_id, supplier_name, country, avg_lead_time_days, on_time_delivery_pct,
    _source_file, _loaded_at, _batch_id
)
FROM (
    SELECT $1, $2, $3, $4, $5,
           METADATA$FILENAME, CURRENT_TIMESTAMP(), '__BATCH_ID__'
    FROM @COCO_FACTORY.RAW.FACTORY_STAGE
)
PATTERN = '.*supplier\\.csv.*'
FILE_FORMAT = (FORMAT_NAME = CSV_CANONICAL)
ON_ERROR = 'CONTINUE';

-- 15. Purchase Order
COPY INTO RAW.PURCHASE_ORDER (
    po_id, supplier_id, part_id, qty, unit_cost_inr, order_date,
    expected_delivery_date, actual_delivery_date, status, order_type, linked_wo_id,
    _source_file, _loaded_at, _batch_id
)
FROM (
    SELECT $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
           METADATA$FILENAME, CURRENT_TIMESTAMP(), '__BATCH_ID__'
    FROM @COCO_FACTORY.RAW.FACTORY_STAGE
)
PATTERN = '.*purchase_order\\.csv.*'
FILE_FORMAT = (FORMAT_NAME = CSV_CANONICAL)
ON_ERROR = 'CONTINUE';

-- 16. Product
COPY INTO RAW.PRODUCT (
    product_id, product_name, product_family, unit_price_inr,
    unit_margin_inr, cycle_time_multiplier,
    _source_file, _loaded_at, _batch_id
)
FROM (
    SELECT $1, $2, $3, $4, $5, $6,
           METADATA$FILENAME, CURRENT_TIMESTAMP(), '__BATCH_ID__'
    FROM @COCO_FACTORY.RAW.FACTORY_STAGE
)
PATTERN = '.*product\\.csv.*'
FILE_FORMAT = (FORMAT_NAME = CSV_CANONICAL)
ON_ERROR = 'CONTINUE';

-- 17. Alert
COPY INTO RAW.ALERT (
    alert_id, machine_id, component_id, sensor_id, ts, severity, alert_type,
    reading_value, threshold_value, message, status, priority_score,
    recommended_action, assigned_to, production_order_id, acknowledged_by,
    acknowledged_ts, closed_ts, wo_id,
    _source_file, _loaded_at, _batch_id
)
FROM (
    SELECT $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19,
           METADATA$FILENAME, CURRENT_TIMESTAMP(), '__BATCH_ID__'
    FROM @COCO_FACTORY.RAW.FACTORY_STAGE
)
PATTERN = '.*alert\\.csv.*'
FILE_FORMAT = (FORMAT_NAME = CSV_CANONICAL)
ON_ERROR = 'CONTINUE';

-- 18. Prediction
COPY INTO RAW.PREDICTION (
    prediction_id, scored_ts, machine_id, suspected_component_id, model_name,
    horizon_days, failure_prob, risk_level, top_features,
    _source_file, _loaded_at, _batch_id
)
FROM (
    SELECT $1, $2, $3, $4, $5, $6, $7, $8, $9,
           METADATA$FILENAME, CURRENT_TIMESTAMP(), '__BATCH_ID__'
    FROM @COCO_FACTORY.RAW.FACTORY_STAGE
)
PATTERN = '.*prediction\\.csv.*'
FILE_FORMAT = (FORMAT_NAME = CSV_CANONICAL)
ON_ERROR = 'CONTINUE';

-- 19. Knowledge Doc
COPY INTO RAW.KNOWLEDGE_DOC (
    doc_id, doc_type, machine_type, component_type, title, content,
    _source_file, _loaded_at, _batch_id
)
FROM (
    SELECT $1, $2, $3, $4, $5, $6,
           METADATA$FILENAME, CURRENT_TIMESTAMP(), '__BATCH_ID__'
    FROM @COCO_FACTORY.RAW.FACTORY_STAGE
)
PATTERN = '.*knowledge_doc\\.csv.*'
FILE_FORMAT = (FORMAT_NAME = CSV_CANONICAL)
ON_ERROR = 'CONTINUE';
