-- 20_core_tables.sql
-- 19 Canonical CORE Conformed Tables with Strict Constraints

USE DATABASE COCO_FACTORY;
USE SCHEMA CORE;

-- 1. Machine Dimension
CREATE TABLE IF NOT EXISTS MACHINE (
    machine_id                  VARCHAR(32) NOT NULL,
    machine_name                VARCHAR(128) NOT NULL,
    machine_type                VARCHAR(64) NOT NULL,
    model                       VARCHAR(64) NOT NULL,
    plant_id                    VARCHAR(32) NOT NULL,
    line_id                     VARCHAR(32) NOT NULL,
    purchase_date               DATE,
    install_date                DATE,
    expected_life_years         INT,
    expected_end_of_life_date   DATE,
    criticality                 VARCHAR(32) NOT NULL,
    ideal_cycle_time_sec        FLOAT,
    rated_power_kw              FLOAT,
    shifts_per_day              INT,
    pm_interval_days            INT,
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_core_machine PRIMARY KEY (machine_id)
);

-- 2. Component Dimension
CREATE TABLE IF NOT EXISTS COMPONENT (
    component_id                VARCHAR(32) NOT NULL,
    machine_id                  VARCHAR(32) NOT NULL,
    component_type              VARCHAR(64) NOT NULL,
    model                       VARCHAR(64),
    purchase_date               DATE,
    install_date                DATE,
    expected_life_hrs           FLOAT,
    operating_hours_used        FLOAT,
    projected_end_of_life_date  DATE,
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_core_component PRIMARY KEY (component_id),
    CONSTRAINT fk_core_component_machine FOREIGN KEY (machine_id) REFERENCES CORE.MACHINE(machine_id)
);

-- 3. Sensor Topology Dimension
CREATE TABLE IF NOT EXISTS SENSOR (
    sensor_id                   VARCHAR(32) NOT NULL,
    machine_id                  VARCHAR(32) NOT NULL,
    component_id                VARCHAR(32),
    sensor_type                 VARCHAR(64) NOT NULL,
    unit                        VARCHAR(32) NOT NULL,
    sampling_rate_hz            FLOAT,
    warn_threshold              FLOAT,
    crit_threshold              FLOAT,
    threshold_direction         VARCHAR(16),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_core_sensor PRIMARY KEY (sensor_id),
    CONSTRAINT fk_core_sensor_machine FOREIGN KEY (machine_id) REFERENCES CORE.MACHINE(machine_id),
    CONSTRAINT fk_core_sensor_component FOREIGN KEY (component_id) REFERENCES CORE.COMPONENT(component_id)
);

-- 4. High-Frequency Sensor Telemetry Fact
CREATE TABLE IF NOT EXISTS SENSOR_READING (
    sensor_id                   VARCHAR(32) NOT NULL,
    ts                          TIMESTAMP_NTZ NOT NULL,
    value                       FLOAT NOT NULL,
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT fk_core_reading_sensor FOREIGN KEY (sensor_id) REFERENCES CORE.SENSOR(sensor_id)
);

-- 5. Hourly Sensor Telemetry Aggregate Fact
CREATE TABLE IF NOT EXISTS SENSOR_READING_HOURLY (
    sensor_id                   VARCHAR(32) NOT NULL,
    ts                          TIMESTAMP_NTZ NOT NULL,
    run_fraction                FLOAT,
    avg_running                 FLOAT,
    min_running                 FLOAT,
    max_running                 FLOAT,
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_core_sensor_reading_hourly PRIMARY KEY (sensor_id, ts),
    CONSTRAINT fk_core_hourly_sensor FOREIGN KEY (sensor_id) REFERENCES CORE.SENSOR(sensor_id)
);

-- 6. Product Dimension
CREATE TABLE IF NOT EXISTS PRODUCT (
    product_id                  VARCHAR(32) NOT NULL,
    product_name                VARCHAR(128) NOT NULL,
    product_family              VARCHAR(64),
    unit_price_inr              NUMBER(14, 2),
    unit_margin_inr             NUMBER(14, 2),
    cycle_time_multiplier       FLOAT,
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_core_product PRIMARY KEY (product_id)
);

-- 7. Production Order Fact
CREATE TABLE IF NOT EXISTS PRODUCTION_ORDER (
    production_order_id         VARCHAR(32) NOT NULL,
    machine_id                  VARCHAR(32),
    product_id                  VARCHAR(32),
    customer                    VARCHAR(128),
    planned_qty                 INT,
    produced_qty                INT,
    planned_start               TIMESTAMP_NTZ,
    planned_end                 TIMESTAMP_NTZ,
    due_date                    TIMESTAMP_NTZ,
    priority                    VARCHAR(32),
    status                      VARCHAR(32),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_core_production_order PRIMARY KEY (production_order_id),
    CONSTRAINT fk_core_order_machine FOREIGN KEY (machine_id) REFERENCES CORE.MACHINE(machine_id),
    CONSTRAINT fk_core_order_product FOREIGN KEY (product_id) REFERENCES CORE.PRODUCT(product_id)
);

-- 8. Production Run Fact
CREATE TABLE IF NOT EXISTS PRODUCTION_RUN (
    run_id                      VARCHAR(32) NOT NULL,
    machine_id                  VARCHAR(32) NOT NULL,
    product_id                  VARCHAR(32),
    production_order_id         VARCHAR(32),
    shift_id                    VARCHAR(32),
    shift_date                  DATE,
    start_ts                    TIMESTAMP_NTZ,
    end_ts                      TIMESTAMP_NTZ,
    planned_time_min            FLOAT,
    planned_maintenance_min     FLOAT,
    unplanned_downtime_min      FLOAT,
    run_time_min                FLOAT,
    ideal_cycle_time_sec        FLOAT,
    total_count                 INT,
    good_count                  INT,
    reject_count                INT,
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_core_production_run PRIMARY KEY (run_id),
    CONSTRAINT fk_core_run_machine FOREIGN KEY (machine_id) REFERENCES CORE.MACHINE(machine_id),
    CONSTRAINT fk_core_run_product FOREIGN KEY (product_id) REFERENCES CORE.PRODUCT(product_id),
    CONSTRAINT fk_core_run_order FOREIGN KEY (production_order_id) REFERENCES CORE.PRODUCTION_ORDER(production_order_id)
);

-- 9. Downtime Event Fact
CREATE TABLE IF NOT EXISTS DOWNTIME_EVENT (
    event_id                    VARCHAR(32) NOT NULL,
    machine_id                  VARCHAR(32) NOT NULL,
    run_id                      VARCHAR(32),
    reason_code                 VARCHAR(32) NOT NULL,
    category                    VARCHAR(64) NOT NULL,
    reason_description          VARCHAR(256),
    start_ts                    TIMESTAMP_NTZ,
    end_ts                      TIMESTAMP_NTZ,
    duration_min                FLOAT,
    wo_id                       VARCHAR(32),
    notes                       VARCHAR(512),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_core_downtime_event PRIMARY KEY (event_id),
    CONSTRAINT fk_core_downtime_machine FOREIGN KEY (machine_id) REFERENCES CORE.MACHINE(machine_id),
    CONSTRAINT fk_core_downtime_run FOREIGN KEY (run_id) REFERENCES CORE.PRODUCTION_RUN(run_id)
);

-- 10. Technician Dimension
CREATE TABLE IF NOT EXISTS TECHNICIAN (
    technician_id               VARCHAR(32) NOT NULL,
    name                        VARCHAR(128) NOT NULL,
    skill_area                  VARCHAR(64),
    shift                       VARCHAR(32),
    hourly_rate_inr             NUMBER(10, 2),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_core_technician PRIMARY KEY (technician_id)
);

-- 11. Maintenance Work Order Dimension/Fact
CREATE TABLE IF NOT EXISTS MAINTENANCE_WORK_ORDER (
    wo_id                       VARCHAR(32) NOT NULL,
    machine_id                  VARCHAR(32) NOT NULL,
    component_id                VARCHAR(32),
    wo_type                     VARCHAR(32) NOT NULL,
    source                      VARCHAR(32),
    priority                    VARCHAR(32) NOT NULL,
    failure_code                VARCHAR(32),
    status                      VARCHAR(32) NOT NULL,
    scheduled_date              DATE,
    opened_ts                   TIMESTAMP_NTZ,
    started_ts                  TIMESTAMP_NTZ,
    closed_ts                   TIMESTAMP_NTZ,
    assigned_to                 VARCHAR(32),
    technicians                 VARCHAR(128),
    labor_hours                 FLOAT,
    parts_cost                  NUMBER(12, 2),
    labor_cost                  NUMBER(12, 2),
    cost                        NUMBER(12, 2),
    prediction_id               VARCHAR(32),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_core_maintenance_wo PRIMARY KEY (wo_id),
    CONSTRAINT fk_core_wo_machine FOREIGN KEY (machine_id) REFERENCES CORE.MACHINE(machine_id),
    CONSTRAINT fk_core_wo_component FOREIGN KEY (component_id) REFERENCES CORE.COMPONENT(component_id)
);

-- 12. Maintenance Execution Log Fact
CREATE TABLE IF NOT EXISTS MAINTENANCE_LOG (
    log_id                      VARCHAR(32) NOT NULL,
    wo_id                       VARCHAR(32),
    machine_id                  VARCHAR(32) NOT NULL,
    component_id                VARCHAR(32),
    technician_id               VARCHAR(32),
    log_ts                      TIMESTAMP_NTZ,
    wo_type                     VARCHAR(32),
    failure_code                VARCHAR(32),
    root_cause_category         VARCHAR(64),
    fault_class                 VARCHAR(64),
    symptom                     VARCHAR(256),
    action_taken                VARCHAR(512),
    downtime_min                FLOAT,
    early_warning_hours         FLOAT,
    note_text                   VARCHAR(1024),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_core_maintenance_log PRIMARY KEY (log_id),
    CONSTRAINT fk_core_log_wo FOREIGN KEY (wo_id) REFERENCES CORE.MAINTENANCE_WORK_ORDER(wo_id),
    CONSTRAINT fk_core_log_machine FOREIGN KEY (machine_id) REFERENCES CORE.MACHINE(machine_id),
    CONSTRAINT fk_core_log_component FOREIGN KEY (component_id) REFERENCES CORE.COMPONENT(component_id),
    CONSTRAINT fk_core_log_technician FOREIGN KEY (technician_id) REFERENCES CORE.TECHNICIAN(technician_id)
);

-- 13. Supplier Dimension
CREATE TABLE IF NOT EXISTS SUPPLIER (
    supplier_id                 VARCHAR(32) NOT NULL,
    supplier_name               VARCHAR(128) NOT NULL,
    country                     VARCHAR(64),
    avg_lead_time_days          FLOAT,
    on_time_delivery_pct        FLOAT,
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_core_supplier PRIMARY KEY (supplier_id)
);

-- 14. Spare Part Dimension
CREATE TABLE IF NOT EXISTS SPARE_PART (
    part_id                     VARCHAR(32) NOT NULL,
    part_name                   VARCHAR(128) NOT NULL,
    part_category               VARCHAR(64),
    compatible_model            VARCHAR(64),
    unit_cost_inr               NUMBER(12, 2),
    supplier_id                 VARCHAR(32),
    lead_time_days              INT,
    stock_qty                   INT NOT NULL DEFAULT 0,
    reorder_level               INT NOT NULL DEFAULT 0,
    reorder_qty                 INT NOT NULL DEFAULT 0,
    warehouse_bin               VARCHAR(32),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_core_spare_part PRIMARY KEY (part_id),
    CONSTRAINT fk_core_part_supplier FOREIGN KEY (supplier_id) REFERENCES CORE.SUPPLIER(supplier_id)
);

-- 15. Purchase Order Fact
CREATE TABLE IF NOT EXISTS PURCHASE_ORDER (
    po_id                       VARCHAR(32) NOT NULL,
    supplier_id                 VARCHAR(32) NOT NULL,
    part_id                     VARCHAR(32) NOT NULL,
    qty                         INT NOT NULL,
    unit_cost_inr               NUMBER(12, 2),
    order_date                  DATE,
    expected_delivery_date      DATE,
    actual_delivery_date        DATE,
    status                      VARCHAR(32),
    order_type                  VARCHAR(32),
    linked_wo_id                VARCHAR(32),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_core_purchase_order PRIMARY KEY (po_id),
    CONSTRAINT fk_core_po_supplier FOREIGN KEY (supplier_id) REFERENCES CORE.SUPPLIER(supplier_id),
    CONSTRAINT fk_core_po_part FOREIGN KEY (part_id) REFERENCES CORE.SPARE_PART(part_id)
);

-- 16. Work Order Part Usage Bridge Fact
CREATE TABLE IF NOT EXISTS WO_PART_USAGE (
    wo_id                       VARCHAR(32) NOT NULL,
    part_id                     VARCHAR(32) NOT NULL,
    qty                         INT NOT NULL,
    unit_cost_inr               NUMBER(12, 2),
    line_cost_inr               NUMBER(12, 2),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT fk_core_usage_wo FOREIGN KEY (wo_id) REFERENCES CORE.MAINTENANCE_WORK_ORDER(wo_id),
    CONSTRAINT fk_core_usage_part FOREIGN KEY (part_id) REFERENCES CORE.SPARE_PART(part_id)
);

-- 17. Alert Fact
CREATE TABLE IF NOT EXISTS ALERT (
    alert_id                    VARCHAR(32) NOT NULL,
    machine_id                  VARCHAR(32) NOT NULL,
    component_id                VARCHAR(32),
    sensor_id                   VARCHAR(32),
    ts                          TIMESTAMP_NTZ NOT NULL,
    severity                    VARCHAR(32) NOT NULL,
    alert_type                  VARCHAR(64) NOT NULL,
    reading_value               FLOAT,
    threshold_value             FLOAT,
    message                     VARCHAR(512),
    status                      VARCHAR(32) NOT NULL,
    priority_score              FLOAT,
    recommended_action          VARCHAR(512),
    assigned_to                 VARCHAR(32),
    production_order_id         VARCHAR(32),
    acknowledged_by             VARCHAR(32),
    acknowledged_ts             TIMESTAMP_NTZ,
    closed_ts                   TIMESTAMP_NTZ,
    wo_id                       VARCHAR(32),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_core_alert PRIMARY KEY (alert_id),
    CONSTRAINT fk_core_alert_machine FOREIGN KEY (machine_id) REFERENCES CORE.MACHINE(machine_id),
    CONSTRAINT fk_core_alert_component FOREIGN KEY (component_id) REFERENCES CORE.COMPONENT(component_id),
    CONSTRAINT fk_core_alert_sensor FOREIGN KEY (sensor_id) REFERENCES CORE.SENSOR(sensor_id)
);

-- 18. Prediction Fact
CREATE TABLE IF NOT EXISTS PREDICTION (
    prediction_id               VARCHAR(32) NOT NULL,
    scored_ts                   TIMESTAMP_NTZ NOT NULL,
    machine_id                  VARCHAR(32) NOT NULL,
    suspected_component_id      VARCHAR(32),
    model_name                  VARCHAR(64) NOT NULL,
    horizon_days                INT NOT NULL,
    failure_prob                FLOAT NOT NULL,
    risk_level                  VARCHAR(32) NOT NULL,
    top_features                VARCHAR(1024),
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_core_prediction PRIMARY KEY (prediction_id),
    CONSTRAINT fk_core_pred_machine FOREIGN KEY (machine_id) REFERENCES CORE.MACHINE(machine_id),
    CONSTRAINT fk_core_pred_component FOREIGN KEY (suspected_component_id) REFERENCES CORE.COMPONENT(component_id)
);

-- 19. Knowledge Document Dimension
CREATE TABLE IF NOT EXISTS KNOWLEDGE_DOC (
    doc_id                      VARCHAR(32) NOT NULL,
    doc_type                    VARCHAR(64),
    machine_type                VARCHAR(64),
    component_type              VARCHAR(64),
    title                       VARCHAR(256) NOT NULL,
    content                     VARCHAR(16777216) NOT NULL,
    _loaded_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_core_knowledge_doc PRIMARY KEY (doc_id)
);
