-- 10_raw_tables.sql
-- 19 Canonical RAW Tables for COCO_FACTORY landing layer

USE DATABASE COCO_FACTORY;
USE SCHEMA RAW;

-- 1. Machine Asset Master
CREATE TABLE IF NOT EXISTS MACHINE (
    machine_id                  VARCHAR(32),
    machine_name                VARCHAR(128),
    machine_type                VARCHAR(64),
    model                       VARCHAR(64),
    plant_id                    VARCHAR(32),
    line_id                     VARCHAR(32),
    purchase_date               VARCHAR(32),
    install_date                VARCHAR(32),
    expected_life_years         VARCHAR(16),
    expected_end_of_life_date   VARCHAR(32),
    criticality                 VARCHAR(32),
    ideal_cycle_time_sec        VARCHAR(16),
    rated_power_kw              VARCHAR(16),
    shifts_per_day              VARCHAR(16),
    pm_interval_days            VARCHAR(16),
    _source_file                VARCHAR(512),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _batch_id                   VARCHAR(64)
);

-- 2. Component Hierarchy
CREATE TABLE IF NOT EXISTS COMPONENT (
    component_id                VARCHAR(32),
    machine_id                  VARCHAR(32),
    component_type              VARCHAR(64),
    model                       VARCHAR(64),
    purchase_date               VARCHAR(32),
    install_date                VARCHAR(32),
    expected_life_hrs           VARCHAR(16),
    operating_hours_used        VARCHAR(16),
    projected_end_of_life_date  VARCHAR(32),
    _source_file                VARCHAR(512),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _batch_id                   VARCHAR(64)
);

-- 3. Sensor Topology
CREATE TABLE IF NOT EXISTS SENSOR (
    sensor_id                   VARCHAR(32),
    machine_id                  VARCHAR(32),
    component_id                VARCHAR(32),
    sensor_type                 VARCHAR(64),
    unit                        VARCHAR(32),
    sampling_rate_hz            VARCHAR(16),
    warn_threshold              VARCHAR(32),
    crit_threshold              VARCHAR(32),
    threshold_direction         VARCHAR(16),
    _source_file                VARCHAR(512),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _batch_id                   VARCHAR(64)
);

-- 4. High-Frequency 1-Minute Sensor Readings
CREATE TABLE IF NOT EXISTS SENSOR_READING (
    sensor_id                   VARCHAR(32),
    ts                          VARCHAR(32),
    value                       VARCHAR(32),
    _source_file                VARCHAR(512),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _batch_id                   VARCHAR(64)
);

-- 5. Aggregated Hourly Sensor Readings
CREATE TABLE IF NOT EXISTS SENSOR_READING_HOURLY (
    sensor_id                   VARCHAR(32),
    ts                          VARCHAR(32),
    run_fraction                VARCHAR(16),
    avg_running                 VARCHAR(32),
    min_running                 VARCHAR(32),
    max_running                 VARCHAR(32),
    _source_file                VARCHAR(512),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _batch_id                   VARCHAR(64)
);

-- 6. Production Orders
CREATE TABLE IF NOT EXISTS PRODUCTION_ORDER (
    production_order_id         VARCHAR(32),
    machine_id                  VARCHAR(32),
    product_id                  VARCHAR(32),
    customer                    VARCHAR(128),
    planned_qty                 VARCHAR(16),
    produced_qty                VARCHAR(16),
    planned_start               VARCHAR(32),
    planned_end                 VARCHAR(32),
    due_date                    VARCHAR(32),
    priority                    VARCHAR(32),
    status                      VARCHAR(32),
    _source_file                VARCHAR(512),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _batch_id                   VARCHAR(64)
);

-- 7. Production Runs
CREATE TABLE IF NOT EXISTS PRODUCTION_RUN (
    run_id                      VARCHAR(32),
    machine_id                  VARCHAR(32),
    product_id                  VARCHAR(32),
    production_order_id         VARCHAR(32),
    shift_id                    VARCHAR(32),
    shift_date                  VARCHAR(32),
    start_ts                    VARCHAR(32),
    end_ts                      VARCHAR(32),
    planned_time_min            VARCHAR(16),
    planned_maintenance_min     VARCHAR(16),
    unplanned_downtime_min      VARCHAR(16),
    run_time_min                VARCHAR(16),
    ideal_cycle_time_sec        VARCHAR(16),
    total_count                 VARCHAR(16),
    good_count                  VARCHAR(16),
    reject_count                VARCHAR(16),
    _source_file                VARCHAR(512),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _batch_id                   VARCHAR(64)
);

-- 8. Downtime Events
CREATE TABLE IF NOT EXISTS DOWNTIME_EVENT (
    event_id                    VARCHAR(32),
    machine_id                  VARCHAR(32),
    run_id                      VARCHAR(32),
    reason_code                 VARCHAR(32),
    category                    VARCHAR(64),
    reason_description          VARCHAR(256),
    start_ts                    VARCHAR(32),
    end_ts                      VARCHAR(32),
    duration_min                VARCHAR(16),
    wo_id                       VARCHAR(32),
    notes                       VARCHAR(512),
    _source_file                VARCHAR(512),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _batch_id                   VARCHAR(64)
);

-- 9. Maintenance Work Orders
CREATE TABLE IF NOT EXISTS MAINTENANCE_WORK_ORDER (
    wo_id                       VARCHAR(32),
    machine_id                  VARCHAR(32),
    component_id                VARCHAR(32),
    wo_type                     VARCHAR(32),
    source                      VARCHAR(32),
    priority                    VARCHAR(32),
    failure_code                VARCHAR(32),
    status                      VARCHAR(32),
    scheduled_date              VARCHAR(32),
    opened_ts                   VARCHAR(32),
    started_ts                  VARCHAR(32),
    closed_ts                   VARCHAR(32),
    assigned_to                 VARCHAR(32),
    technicians                 VARCHAR(128),
    labor_hours                 VARCHAR(16),
    parts_cost                  VARCHAR(32),
    labor_cost                  VARCHAR(32),
    cost                        VARCHAR(32),
    prediction_id               VARCHAR(32),
    _source_file                VARCHAR(512),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _batch_id                   VARCHAR(64)
);

-- 10. Maintenance Technicians
CREATE TABLE IF NOT EXISTS TECHNICIAN (
    technician_id               VARCHAR(32),
    name                        VARCHAR(128),
    skill_area                  VARCHAR(64),
    shift                       VARCHAR(32),
    hourly_rate_inr             VARCHAR(16),
    _source_file                VARCHAR(512),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _batch_id                   VARCHAR(64)
);

-- 11. Maintenance Execution Logs
CREATE TABLE IF NOT EXISTS MAINTENANCE_LOG (
    log_id                      VARCHAR(32),
    wo_id                       VARCHAR(32),
    machine_id                  VARCHAR(32),
    component_id                VARCHAR(32),
    technician_id               VARCHAR(32),
    log_ts                      VARCHAR(32),
    wo_type                     VARCHAR(32),
    failure_code                VARCHAR(32),
    root_cause_category         VARCHAR(64),
    fault_class                 VARCHAR(64),
    symptom                     VARCHAR(256),
    action_taken                VARCHAR(512),
    downtime_min                VARCHAR(16),
    early_warning_hours         VARCHAR(16),
    note_text                   VARCHAR(1024),
    _source_file                VARCHAR(512),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _batch_id                   VARCHAR(64)
);

-- 12. Work Order Part Usages
CREATE TABLE IF NOT EXISTS WO_PART_USAGE (
    wo_id                       VARCHAR(32),
    part_id                     VARCHAR(32),
    qty                         VARCHAR(16),
    unit_cost_inr               VARCHAR(32),
    line_cost_inr               VARCHAR(32),
    _source_file                VARCHAR(512),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _batch_id                   VARCHAR(64)
);

-- 13. Spare Parts Catalog & Inventory
CREATE TABLE IF NOT EXISTS SPARE_PART (
    part_id                     VARCHAR(32),
    part_name                   VARCHAR(128),
    part_category               VARCHAR(64),
    compatible_model            VARCHAR(64),
    unit_cost_inr               VARCHAR(32),
    supplier_id                 VARCHAR(32),
    lead_time_days              VARCHAR(16),
    stock_qty                   VARCHAR(16),
    reorder_level               VARCHAR(16),
    reorder_qty                 VARCHAR(16),
    warehouse_bin               VARCHAR(32),
    _source_file                VARCHAR(512),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _batch_id                   VARCHAR(64)
);

-- 14. Suppliers
CREATE TABLE IF NOT EXISTS SUPPLIER (
    supplier_id                 VARCHAR(32),
    supplier_name               VARCHAR(128),
    country                     VARCHAR(64),
    avg_lead_time_days          VARCHAR(16),
    on_time_delivery_pct        VARCHAR(16),
    _source_file                VARCHAR(512),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _batch_id                   VARCHAR(64)
);

-- 15. Purchase Orders
CREATE TABLE IF NOT EXISTS PURCHASE_ORDER (
    po_id                       VARCHAR(32),
    supplier_id                 VARCHAR(32),
    part_id                     VARCHAR(32),
    qty                         VARCHAR(16),
    unit_cost_inr               VARCHAR(32),
    order_date                  VARCHAR(32),
    expected_delivery_date      VARCHAR(32),
    actual_delivery_date        VARCHAR(32),
    status                      VARCHAR(32),
    order_type                  VARCHAR(32),
    linked_wo_id                VARCHAR(32),
    _source_file                VARCHAR(512),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _batch_id                   VARCHAR(64)
);

-- 16. Products
CREATE TABLE IF NOT EXISTS PRODUCT (
    product_id                  VARCHAR(32),
    product_name                VARCHAR(128),
    product_family              VARCHAR(64),
    unit_price_inr              VARCHAR(32),
    unit_margin_inr             VARCHAR(32),
    cycle_time_multiplier       VARCHAR(16),
    _source_file                VARCHAR(512),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _batch_id                   VARCHAR(64)
);

-- 17. Operational Alerts
CREATE TABLE IF NOT EXISTS ALERT (
    alert_id                    VARCHAR(32),
    machine_id                  VARCHAR(32),
    component_id                VARCHAR(32),
    sensor_id                   VARCHAR(32),
    ts                          VARCHAR(32),
    severity                    VARCHAR(32),
    alert_type                  VARCHAR(64),
    reading_value               VARCHAR(32),
    threshold_value             VARCHAR(32),
    message                     VARCHAR(512),
    status                      VARCHAR(32),
    priority_score              VARCHAR(16),
    recommended_action          VARCHAR(512),
    assigned_to                 VARCHAR(32),
    production_order_id         VARCHAR(32),
    acknowledged_by             VARCHAR(32),
    acknowledged_ts             VARCHAR(32),
    closed_ts                   VARCHAR(32),
    wo_id                       VARCHAR(32),
    _source_file                VARCHAR(512),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _batch_id                   VARCHAR(64)
);

-- 18. Predictive Degradation Scores
CREATE TABLE IF NOT EXISTS PREDICTION (
    prediction_id               VARCHAR(32),
    scored_ts                   VARCHAR(32),
    machine_id                  VARCHAR(32),
    suspected_component_id      VARCHAR(32),
    model_name                  VARCHAR(64),
    horizon_days                VARCHAR(16),
    failure_prob                VARCHAR(32),
    risk_level                  VARCHAR(32),
    top_features                VARCHAR(1024),
    _source_file                VARCHAR(512),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _batch_id                   VARCHAR(64)
);

-- 19. Unstructured Knowledge Documents
CREATE TABLE IF NOT EXISTS KNOWLEDGE_DOC (
    doc_id                      VARCHAR(32),
    doc_type                    VARCHAR(64),
    machine_type                VARCHAR(64),
    component_type              VARCHAR(64),
    title                       VARCHAR(256),
    content                     VARCHAR(16777216),
    _source_file                VARCHAR(512),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _batch_id                   VARCHAR(64)
);
