-- 80_core_conformed_transforms.sql
-- ELT transforms from RAW landing tables to CORE conformed tables with type casting and deduplication

USE DATABASE COCO_FACTORY;

-- 1. Transform MACHINE
MERGE INTO CORE.MACHINE t
USING (
    SELECT DISTINCT
        TRIM(machine_id) AS machine_id,
        TRIM(machine_name) AS machine_name,
        TRIM(machine_type) AS machine_type,
        TRIM(model) AS model,
        TRIM(plant_id) AS plant_id,
        TRIM(line_id) AS line_id,
        TRY_TO_DATE(purchase_date) AS purchase_date,
        TRY_TO_DATE(install_date) AS install_date,
        TRY_TO_NUMBER(expected_life_years) AS expected_life_years,
        TRY_TO_DATE(expected_end_of_life_date) AS expected_end_of_life_date,
        TRIM(criticality) AS criticality,
        TRY_TO_DOUBLE(ideal_cycle_time_sec) AS ideal_cycle_time_sec,
        TRY_TO_DOUBLE(rated_power_kw) AS rated_power_kw,
        TRY_TO_NUMBER(shifts_per_day) AS shifts_per_day,
        TRY_TO_NUMBER(pm_interval_days) AS pm_interval_days
    FROM RAW.MACHINE
    WHERE machine_id IS NOT NULL AND TRIM(machine_id) <> ''
) s
ON t.machine_id = s.machine_id
WHEN MATCHED THEN UPDATE SET
    t.machine_name = s.machine_name,
    t.machine_type = s.machine_type,
    t.model = s.model,
    t.plant_id = s.plant_id,
    t.line_id = s.line_id,
    t.purchase_date = s.purchase_date,
    t.install_date = s.install_date,
    t.expected_life_years = s.expected_life_years,
    t.expected_end_of_life_date = s.expected_end_of_life_date,
    t.criticality = s.criticality,
    t.ideal_cycle_time_sec = s.ideal_cycle_time_sec,
    t.rated_power_kw = s.rated_power_kw,
    t.shifts_per_day = s.shifts_per_day,
    t.pm_interval_days = s.pm_interval_days,
    t._loaded_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    machine_id, machine_name, machine_type, model, plant_id, line_id,
    purchase_date, install_date, expected_life_years, expected_end_of_life_date,
    criticality, ideal_cycle_time_sec, rated_power_kw, shifts_per_day, pm_interval_days
) VALUES (
    s.machine_id, s.machine_name, s.machine_type, s.model, s.plant_id, s.line_id,
    s.purchase_date, s.install_date, s.expected_life_years, s.expected_end_of_life_date,
    s.criticality, s.ideal_cycle_time_sec, s.rated_power_kw, s.shifts_per_day, s.pm_interval_days
);

-- 2. Transform COMPONENT
MERGE INTO CORE.COMPONENT t
USING (
    SELECT DISTINCT
        TRIM(component_id) AS component_id,
        TRIM(machine_id) AS machine_id,
        TRIM(component_type) AS component_type,
        TRIM(model) AS model,
        TRY_TO_DATE(purchase_date) AS purchase_date,
        TRY_TO_DATE(install_date) AS install_date,
        TRY_TO_DOUBLE(expected_life_hrs) AS expected_life_hrs,
        TRY_TO_DOUBLE(operating_hours_used) AS operating_hours_used,
        TRY_TO_DATE(projected_end_of_life_date) AS projected_end_of_life_date
    FROM RAW.COMPONENT
    WHERE component_id IS NOT NULL AND TRIM(component_id) <> ''
) s
ON t.component_id = s.component_id
WHEN MATCHED THEN UPDATE SET
    t.machine_id = s.machine_id,
    t.component_type = s.component_type,
    t.model = s.model,
    t.purchase_date = s.purchase_date,
    t.install_date = s.install_date,
    t.expected_life_hrs = s.expected_life_hrs,
    t.operating_hours_used = s.operating_hours_used,
    t.projected_end_of_life_date = s.projected_end_of_life_date,
    t._loaded_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    component_id, machine_id, component_type, model, purchase_date,
    install_date, expected_life_hrs, operating_hours_used, projected_end_of_life_date
) VALUES (
    s.component_id, s.machine_id, s.component_type, s.model, s.purchase_date,
    s.install_date, s.expected_life_hrs, s.operating_hours_used, s.projected_end_of_life_date
);

-- 3. Transform SENSOR
MERGE INTO CORE.SENSOR t
USING (
    SELECT DISTINCT
        TRIM(sensor_id) AS sensor_id,
        TRIM(machine_id) AS machine_id,
        TRIM(component_id) AS component_id,
        TRIM(sensor_type) AS sensor_type,
        TRIM(unit) AS unit,
        TRY_TO_DOUBLE(sampling_rate_hz) AS sampling_rate_hz,
        TRY_TO_DOUBLE(warn_threshold) AS warn_threshold,
        TRY_TO_DOUBLE(crit_threshold) AS crit_threshold,
        TRIM(threshold_direction) AS threshold_direction
    FROM RAW.SENSOR
    WHERE sensor_id IS NOT NULL AND TRIM(sensor_id) <> ''
) s
ON t.sensor_id = s.sensor_id
WHEN MATCHED THEN UPDATE SET
    t.machine_id = s.machine_id,
    t.component_id = s.component_id,
    t.sensor_type = s.sensor_type,
    t.unit = s.unit,
    t.sampling_rate_hz = s.sampling_rate_hz,
    t.warn_threshold = s.warn_threshold,
    t.crit_threshold = s.crit_threshold,
    t.threshold_direction = s.threshold_direction,
    t._loaded_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    sensor_id, machine_id, component_id, sensor_type, unit,
    sampling_rate_hz, warn_threshold, crit_threshold, threshold_direction
) VALUES (
    s.sensor_id, s.machine_id, s.component_id, s.sensor_type, s.unit,
    s.sampling_rate_hz, s.warn_threshold, s.crit_threshold, s.threshold_direction
);

-- 4. Transform TECHNICIAN
MERGE INTO CORE.TECHNICIAN t
USING (
    SELECT DISTINCT
        TRIM(technician_id) AS technician_id,
        TRIM(name) AS name,
        TRIM(skill_area) AS skill_area,
        TRIM(shift) AS shift,
        TRY_TO_NUMBER(hourly_rate_inr, 10, 2) AS hourly_rate_inr
    FROM RAW.TECHNICIAN
    WHERE technician_id IS NOT NULL AND TRIM(technician_id) <> ''
) s
ON t.technician_id = s.technician_id
WHEN MATCHED THEN UPDATE SET
    t.name = s.name,
    t.skill_area = s.skill_area,
    t.shift = s.shift,
    t.hourly_rate_inr = s.hourly_rate_inr,
    t._loaded_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    technician_id, name, skill_area, shift, hourly_rate_inr
) VALUES (
    s.technician_id, s.name, s.skill_area, s.shift, s.hourly_rate_inr
);

-- 5. Transform PRODUCT
MERGE INTO CORE.PRODUCT t
USING (
    SELECT DISTINCT
        TRIM(product_id) AS product_id,
        TRIM(product_name) AS product_name,
        TRIM(product_family) AS product_family,
        TRY_TO_NUMBER(unit_price_inr, 14, 2) AS unit_price_inr,
        TRY_TO_NUMBER(unit_margin_inr, 14, 2) AS unit_margin_inr,
        TRY_TO_DOUBLE(cycle_time_multiplier) AS cycle_time_multiplier
    FROM RAW.PRODUCT
    WHERE product_id IS NOT NULL AND TRIM(product_id) <> ''
) s
ON t.product_id = s.product_id
WHEN MATCHED THEN UPDATE SET
    t.product_name = s.product_name,
    t.product_family = s.product_family,
    t.unit_price_inr = s.unit_price_inr,
    t.unit_margin_inr = s.unit_margin_inr,
    t.cycle_time_multiplier = s.cycle_time_multiplier,
    t._loaded_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    product_id, product_name, product_family, unit_price_inr, unit_margin_inr, cycle_time_multiplier
) VALUES (
    s.product_id, s.product_name, s.product_family, s.unit_price_inr, s.unit_margin_inr, s.cycle_time_multiplier
);

-- 6. Transform SUPPLIER
MERGE INTO CORE.SUPPLIER t
USING (
    SELECT DISTINCT
        TRIM(supplier_id) AS supplier_id,
        TRIM(supplier_name) AS supplier_name,
        TRIM(country) AS country,
        TRY_TO_DOUBLE(avg_lead_time_days) AS avg_lead_time_days,
        TRY_TO_DOUBLE(on_time_delivery_pct) AS on_time_delivery_pct
    FROM RAW.SUPPLIER
    WHERE supplier_id IS NOT NULL AND TRIM(supplier_id) <> ''
) s
ON t.supplier_id = s.supplier_id
WHEN MATCHED THEN UPDATE SET
    t.supplier_name = s.supplier_name,
    t.country = s.country,
    t.avg_lead_time_days = s.avg_lead_time_days,
    t.on_time_delivery_pct = s.on_time_delivery_pct,
    t._loaded_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    supplier_id, supplier_name, country, avg_lead_time_days, on_time_delivery_pct
) VALUES (
    s.supplier_id, s.supplier_name, s.country, s.avg_lead_time_days, s.on_time_delivery_pct
);

-- 7. Transform SPARE_PART
MERGE INTO CORE.SPARE_PART t
USING (
    SELECT DISTINCT
        TRIM(part_id) AS part_id,
        TRIM(part_name) AS part_name,
        TRIM(part_category) AS part_category,
        TRIM(compatible_model) AS compatible_model,
        TRY_TO_NUMBER(unit_cost_inr, 12, 2) AS unit_cost_inr,
        TRIM(supplier_id) AS supplier_id,
        TRY_TO_NUMBER(lead_time_days) AS lead_time_days,
        COALESCE(TRY_TO_NUMBER(stock_qty), 0) AS stock_qty,
        COALESCE(TRY_TO_NUMBER(reorder_level), 0) AS reorder_level,
        COALESCE(TRY_TO_NUMBER(reorder_qty), 0) AS reorder_qty,
        TRIM(warehouse_bin) AS warehouse_bin
    FROM RAW.SPARE_PART
    WHERE part_id IS NOT NULL AND TRIM(part_id) <> ''
) s
ON t.part_id = s.part_id
WHEN MATCHED THEN UPDATE SET
    t.part_name = s.part_name,
    t.part_category = s.part_category,
    t.compatible_model = s.compatible_model,
    t.unit_cost_inr = s.unit_cost_inr,
    t.supplier_id = s.supplier_id,
    t.lead_time_days = s.lead_time_days,
    t.stock_qty = s.stock_qty,
    t.reorder_level = s.reorder_level,
    t.reorder_qty = s.reorder_qty,
    t.warehouse_bin = s.warehouse_bin,
    t._loaded_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    part_id, part_name, part_category, compatible_model, unit_cost_inr,
    supplier_id, lead_time_days, stock_qty, reorder_level, reorder_qty, warehouse_bin
) VALUES (
    s.part_id, s.part_name, s.part_category, s.compatible_model, s.unit_cost_inr,
    s.supplier_id, s.lead_time_days, s.stock_qty, s.reorder_level, s.reorder_qty, s.warehouse_bin
);

-- 8. Transform PURCHASE_ORDER
MERGE INTO CORE.PURCHASE_ORDER t
USING (
    SELECT DISTINCT
        TRIM(po_id) AS po_id,
        TRIM(supplier_id) AS supplier_id,
        TRIM(part_id) AS part_id,
        COALESCE(TRY_TO_NUMBER(qty), 0) AS qty,
        TRY_TO_NUMBER(unit_cost_inr, 12, 2) AS unit_cost_inr,
        TRY_TO_DATE(order_date) AS order_date,
        TRY_TO_DATE(expected_delivery_date) AS expected_delivery_date,
        TRY_TO_DATE(actual_delivery_date) AS actual_delivery_date,
        TRIM(status) AS status,
        TRIM(order_type) AS order_type,
        TRIM(linked_wo_id) AS linked_wo_id
    FROM RAW.PURCHASE_ORDER
    WHERE po_id IS NOT NULL AND TRIM(po_id) <> ''
) s
ON t.po_id = s.po_id
WHEN MATCHED THEN UPDATE SET
    t.supplier_id = s.supplier_id,
    t.part_id = s.part_id,
    t.qty = s.qty,
    t.unit_cost_inr = s.unit_cost_inr,
    t.order_date = s.order_date,
    t.expected_delivery_date = s.expected_delivery_date,
    t.actual_delivery_date = s.actual_delivery_date,
    t.status = s.status,
    t.order_type = s.order_type,
    t.linked_wo_id = s.linked_wo_id,
    t._loaded_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    po_id, supplier_id, part_id, qty, unit_cost_inr, order_date,
    expected_delivery_date, actual_delivery_date, status, order_type, linked_wo_id
) VALUES (
    s.po_id, s.supplier_id, s.part_id, s.qty, s.unit_cost_inr, s.order_date,
    s.expected_delivery_date, s.actual_delivery_date, s.status, s.order_type, s.linked_wo_id
);

-- 9. Transform PRODUCTION_ORDER
MERGE INTO CORE.PRODUCTION_ORDER t
USING (
    SELECT DISTINCT
        TRIM(production_order_id) AS production_order_id,
        TRIM(machine_id) AS machine_id,
        TRIM(product_id) AS product_id,
        TRIM(customer) AS customer,
        TRY_TO_NUMBER(planned_qty) AS planned_qty,
        TRY_TO_NUMBER(produced_qty) AS produced_qty,
        TRY_TO_TIMESTAMP_NTZ(planned_start) AS planned_start,
        TRY_TO_TIMESTAMP_NTZ(planned_end) AS planned_end,
        TRY_TO_TIMESTAMP_NTZ(due_date) AS due_date,
        TRIM(priority) AS priority,
        TRIM(status) AS status
    FROM RAW.PRODUCTION_ORDER
    WHERE production_order_id IS NOT NULL AND TRIM(production_order_id) <> ''
) s
ON t.production_order_id = s.production_order_id
WHEN MATCHED THEN UPDATE SET
    t.machine_id = s.machine_id,
    t.product_id = s.product_id,
    t.customer = s.customer,
    t.planned_qty = s.planned_qty,
    t.produced_qty = s.produced_qty,
    t.planned_start = s.planned_start,
    t.planned_end = s.planned_end,
    t.due_date = s.due_date,
    t.priority = s.priority,
    t.status = s.status,
    t._loaded_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    production_order_id, machine_id, product_id, customer, planned_qty,
    produced_qty, planned_start, planned_end, due_date, priority, status
) VALUES (
    s.production_order_id, s.machine_id, s.product_id, s.customer, s.planned_qty,
    s.produced_qty, s.planned_start, s.planned_end, s.due_date, s.priority, s.status
);

-- 10. Transform PRODUCTION_RUN
MERGE INTO CORE.PRODUCTION_RUN t
USING (
    SELECT DISTINCT
        TRIM(run_id) AS run_id,
        TRIM(machine_id) AS machine_id,
        TRIM(product_id) AS product_id,
        TRIM(production_order_id) AS production_order_id,
        TRIM(shift_id) AS shift_id,
        TRY_TO_DATE(shift_date) AS shift_date,
        TRY_TO_TIMESTAMP_NTZ(start_ts) AS start_ts,
        TRY_TO_TIMESTAMP_NTZ(end_ts) AS end_ts,
        TRY_TO_DOUBLE(planned_time_min) AS planned_time_min,
        TRY_TO_DOUBLE(planned_maintenance_min) AS planned_maintenance_min,
        TRY_TO_DOUBLE(unplanned_downtime_min) AS unplanned_downtime_min,
        TRY_TO_DOUBLE(run_time_min) AS run_time_min,
        TRY_TO_DOUBLE(ideal_cycle_time_sec) AS ideal_cycle_time_sec,
        TRY_TO_NUMBER(total_count) AS total_count,
        TRY_TO_NUMBER(good_count) AS good_count,
        TRY_TO_NUMBER(reject_count) AS reject_count
    FROM RAW.PRODUCTION_RUN
    WHERE run_id IS NOT NULL AND TRIM(run_id) <> ''
) s
ON t.run_id = s.run_id
WHEN MATCHED THEN UPDATE SET
    t.machine_id = s.machine_id,
    t.product_id = s.product_id,
    t.production_order_id = s.production_order_id,
    t.shift_id = s.shift_id,
    t.shift_date = s.shift_date,
    t.start_ts = s.start_ts,
    t.end_ts = s.end_ts,
    t.planned_time_min = s.planned_time_min,
    t.planned_maintenance_min = s.planned_maintenance_min,
    t.unplanned_downtime_min = s.unplanned_downtime_min,
    t.run_time_min = s.run_time_min,
    t.ideal_cycle_time_sec = s.ideal_cycle_time_sec,
    t.total_count = s.total_count,
    t.good_count = s.good_count,
    t.reject_count = s.reject_count,
    t._loaded_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    run_id, machine_id, product_id, production_order_id, shift_id, shift_date,
    start_ts, end_ts, planned_time_min, planned_maintenance_min,
    unplanned_downtime_min, run_time_min, ideal_cycle_time_sec, total_count,
    good_count, reject_count
) VALUES (
    s.run_id, s.machine_id, s.product_id, s.production_order_id, s.shift_id, s.shift_date,
    s.start_ts, s.end_ts, s.planned_time_min, s.planned_maintenance_min,
    s.unplanned_downtime_min, s.run_time_min, s.ideal_cycle_time_sec, s.total_count,
    s.good_count, s.reject_count
);

-- 11. Transform MAINTENANCE_WORK_ORDER
MERGE INTO CORE.MAINTENANCE_WORK_ORDER t
USING (
    SELECT DISTINCT
        TRIM(wo_id) AS wo_id,
        TRIM(machine_id) AS machine_id,
        TRIM(component_id) AS component_id,
        TRIM(wo_type) AS wo_type,
        TRIM(source) AS source,
        TRIM(priority) AS priority,
        TRIM(failure_code) AS failure_code,
        TRIM(status) AS status,
        TRY_TO_DATE(scheduled_date) AS scheduled_date,
        TRY_TO_TIMESTAMP_NTZ(opened_ts) AS opened_ts,
        TRY_TO_TIMESTAMP_NTZ(started_ts) AS started_ts,
        TRY_TO_TIMESTAMP_NTZ(closed_ts) AS closed_ts,
        TRIM(assigned_to) AS assigned_to,
        TRIM(technicians) AS technicians,
        TRY_TO_DOUBLE(labor_hours) AS labor_hours,
        TRY_TO_NUMBER(parts_cost, 12, 2) AS parts_cost,
        TRY_TO_NUMBER(labor_cost, 12, 2) AS labor_cost,
        TRY_TO_NUMBER(cost, 12, 2) AS cost,
        TRIM(prediction_id) AS prediction_id
    FROM RAW.MAINTENANCE_WORK_ORDER
    WHERE wo_id IS NOT NULL AND TRIM(wo_id) <> ''
) s
ON t.wo_id = s.wo_id
WHEN MATCHED THEN UPDATE SET
    t.machine_id = s.machine_id,
    t.component_id = s.component_id,
    t.wo_type = s.wo_type,
    t.source = s.source,
    t.priority = s.priority,
    t.failure_code = s.failure_code,
    t.status = s.status,
    t.scheduled_date = s.scheduled_date,
    t.opened_ts = s.opened_ts,
    t.started_ts = s.started_ts,
    t.closed_ts = s.closed_ts,
    t.assigned_to = s.assigned_to,
    t.technicians = s.technicians,
    t.labor_hours = s.labor_hours,
    t.parts_cost = s.parts_cost,
    t.labor_cost = s.labor_cost,
    t.cost = s.cost,
    t.prediction_id = s.prediction_id,
    t._loaded_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    wo_id, machine_id, component_id, wo_type, source, priority, failure_code,
    status, scheduled_date, opened_ts, started_ts, closed_ts, assigned_to,
    technicians, labor_hours, parts_cost, labor_cost, cost, prediction_id
) VALUES (
    s.wo_id, s.machine_id, s.component_id, s.wo_type, s.source, s.priority, s.failure_code,
    s.status, s.scheduled_date, s.opened_ts, s.started_ts, s.closed_ts, s.assigned_to,
    s.technicians, s.labor_hours, s.parts_cost, s.labor_cost, s.cost, s.prediction_id
);

-- 12. Transform DOWNTIME_EVENT
MERGE INTO CORE.DOWNTIME_EVENT t
USING (
    SELECT DISTINCT
        TRIM(event_id) AS event_id,
        TRIM(machine_id) AS machine_id,
        TRIM(run_id) AS run_id,
        TRIM(reason_code) AS reason_code,
        TRIM(category) AS category,
        TRIM(reason_description) AS reason_description,
        TRY_TO_TIMESTAMP_NTZ(start_ts) AS start_ts,
        TRY_TO_TIMESTAMP_NTZ(end_ts) AS end_ts,
        TRY_TO_DOUBLE(duration_min) AS duration_min,
        TRIM(wo_id) AS wo_id,
        TRIM(notes) AS notes
    FROM RAW.DOWNTIME_EVENT
    WHERE event_id IS NOT NULL AND TRIM(event_id) <> ''
) s
ON t.event_id = s.event_id
WHEN MATCHED THEN UPDATE SET
    t.machine_id = s.machine_id,
    t.run_id = s.run_id,
    t.reason_code = s.reason_code,
    t.category = s.category,
    t.reason_description = s.reason_description,
    t.start_ts = s.start_ts,
    t.end_ts = s.end_ts,
    t.duration_min = s.duration_min,
    t.wo_id = s.wo_id,
    t.notes = s.notes,
    t._loaded_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    event_id, machine_id, run_id, reason_code, category,
    reason_description, start_ts, end_ts, duration_min, wo_id, notes
) VALUES (
    s.event_id, s.machine_id, s.run_id, s.reason_code, s.category,
    s.reason_description, s.start_ts, s.end_ts, s.duration_min, s.wo_id, s.notes
);

-- 13. Transform MAINTENANCE_LOG
MERGE INTO CORE.MAINTENANCE_LOG t
USING (
    SELECT DISTINCT
        TRIM(log_id) AS log_id,
        TRIM(wo_id) AS wo_id,
        TRIM(machine_id) AS machine_id,
        TRIM(component_id) AS component_id,
        TRIM(technician_id) AS technician_id,
        TRY_TO_TIMESTAMP_NTZ(log_ts) AS log_ts,
        TRIM(wo_type) AS wo_type,
        TRIM(failure_code) AS failure_code,
        TRIM(root_cause_category) AS root_cause_category,
        TRIM(fault_class) AS fault_class,
        TRIM(symptom) AS symptom,
        TRIM(action_taken) AS action_taken,
        TRY_TO_DOUBLE(downtime_min) AS downtime_min,
        TRY_TO_DOUBLE(early_warning_hours) AS early_warning_hours,
        TRIM(note_text) AS note_text
    FROM RAW.MAINTENANCE_LOG
    WHERE log_id IS NOT NULL AND TRIM(log_id) <> ''
) s
ON t.log_id = s.log_id
WHEN MATCHED THEN UPDATE SET
    t.wo_id = s.wo_id,
    t.machine_id = s.machine_id,
    t.component_id = s.component_id,
    t.technician_id = s.technician_id,
    t.log_ts = s.log_ts,
    t.wo_type = s.wo_type,
    t.failure_code = s.failure_code,
    t.root_cause_category = s.root_cause_category,
    t.fault_class = s.fault_class,
    t.symptom = s.symptom,
    t.action_taken = s.action_taken,
    t.downtime_min = s.downtime_min,
    t.early_warning_hours = s.early_warning_hours,
    t.note_text = s.note_text,
    t._loaded_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    log_id, wo_id, machine_id, component_id, technician_id, log_ts, wo_type,
    failure_code, root_cause_category, fault_class, symptom, action_taken,
    downtime_min, early_warning_hours, note_text
) VALUES (
    s.log_id, s.wo_id, s.machine_id, s.component_id, s.technician_id, s.log_ts, s.wo_type,
    s.failure_code, s.root_cause_category, s.fault_class, s.symptom, s.action_taken,
    s.downtime_min, s.early_warning_hours, s.note_text
);

-- 14. Transform WO_PART_USAGE
DELETE FROM CORE.WO_PART_USAGE;
INSERT INTO CORE.WO_PART_USAGE (wo_id, part_id, qty, unit_cost_inr, line_cost_inr)
SELECT DISTINCT
    TRIM(wo_id) AS wo_id,
    TRIM(part_id) AS part_id,
    COALESCE(TRY_TO_NUMBER(qty), 0) AS qty,
    TRY_TO_NUMBER(unit_cost_inr, 12, 2) AS unit_cost_inr,
    TRY_TO_NUMBER(line_cost_inr, 12, 2) AS line_cost_inr
FROM RAW.WO_PART_USAGE
WHERE wo_id IS NOT NULL AND part_id IS NOT NULL;

-- 15. Transform ALERT
MERGE INTO CORE.ALERT t
USING (
    SELECT DISTINCT
        TRIM(alert_id) AS alert_id,
        TRIM(machine_id) AS machine_id,
        TRIM(component_id) AS component_id,
        TRIM(sensor_id) AS sensor_id,
        TRY_TO_TIMESTAMP_NTZ(ts) AS ts,
        TRIM(severity) AS severity,
        TRIM(alert_type) AS alert_type,
        TRY_TO_DOUBLE(reading_value) AS reading_value,
        TRY_TO_DOUBLE(threshold_value) AS threshold_value,
        TRIM(message) AS message,
        TRIM(status) AS status,
        TRY_TO_DOUBLE(priority_score) AS priority_score,
        TRIM(recommended_action) AS recommended_action,
        TRIM(assigned_to) AS assigned_to,
        TRIM(production_order_id) AS production_order_id,
        TRIM(acknowledged_by) AS acknowledged_by,
        TRY_TO_TIMESTAMP_NTZ(acknowledged_ts) AS acknowledged_ts,
        TRY_TO_TIMESTAMP_NTZ(closed_ts) AS closed_ts,
        TRIM(wo_id) AS wo_id
    FROM RAW.ALERT
    WHERE alert_id IS NOT NULL AND TRIM(alert_id) <> ''
) s
ON t.alert_id = s.alert_id
WHEN MATCHED THEN UPDATE SET
    t.machine_id = s.machine_id,
    t.component_id = s.component_id,
    t.sensor_id = s.sensor_id,
    t.ts = s.ts,
    t.severity = s.severity,
    t.alert_type = s.alert_type,
    t.reading_value = s.reading_value,
    t.threshold_value = s.threshold_value,
    t.message = s.message,
    t.status = s.status,
    t.priority_score = s.priority_score,
    t.recommended_action = s.recommended_action,
    t.assigned_to = s.assigned_to,
    t.production_order_id = s.production_order_id,
    t.acknowledged_by = s.acknowledged_by,
    t.acknowledged_ts = s.acknowledged_ts,
    t.closed_ts = s.closed_ts,
    t.wo_id = s.wo_id,
    t._loaded_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    alert_id, machine_id, component_id, sensor_id, ts, severity, alert_type,
    reading_value, threshold_value, message, status, priority_score,
    recommended_action, assigned_to, production_order_id, acknowledged_by,
    acknowledged_ts, closed_ts, wo_id
) VALUES (
    s.alert_id, s.machine_id, s.component_id, s.sensor_id, s.ts, s.severity, s.alert_type,
    s.reading_value, s.threshold_value, s.message, s.status, s.priority_score,
    s.recommended_action, s.assigned_to, s.production_order_id, s.acknowledged_by,
    s.acknowledged_ts, s.closed_ts, s.wo_id
);

-- 16. Transform PREDICTION
MERGE INTO CORE.PREDICTION t
USING (
    SELECT DISTINCT
        TRIM(prediction_id) AS prediction_id,
        TRY_TO_TIMESTAMP_NTZ(scored_ts) AS scored_ts,
        TRIM(machine_id) AS machine_id,
        TRIM(suspected_component_id) AS suspected_component_id,
        TRIM(model_name) AS model_name,
        COALESCE(TRY_TO_NUMBER(horizon_days), 7) AS horizon_days,
        TRY_TO_DOUBLE(failure_prob) AS failure_prob,
        TRIM(risk_level) AS risk_level,
        TRIM(top_features) AS top_features
    FROM RAW.PREDICTION
    WHERE prediction_id IS NOT NULL AND TRIM(prediction_id) <> ''
) s
ON t.prediction_id = s.prediction_id
WHEN MATCHED THEN UPDATE SET
    t.scored_ts = s.scored_ts,
    t.machine_id = s.machine_id,
    t.suspected_component_id = s.suspected_component_id,
    t.model_name = s.model_name,
    t.horizon_days = s.horizon_days,
    t.failure_prob = s.failure_prob,
    t.risk_level = s.risk_level,
    t.top_features = s.top_features,
    t._loaded_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    prediction_id, scored_ts, machine_id, suspected_component_id, model_name,
    horizon_days, failure_prob, risk_level, top_features
) VALUES (
    s.prediction_id, s.scored_ts, s.machine_id, s.suspected_component_id, s.model_name,
    s.horizon_days, s.failure_prob, s.risk_level, s.top_features
);

-- 17. Transform KNOWLEDGE_DOC
MERGE INTO CORE.KNOWLEDGE_DOC t
USING (
    SELECT DISTINCT
        TRIM(doc_id) AS doc_id,
        TRIM(doc_type) AS doc_type,
        TRIM(machine_type) AS machine_type,
        TRIM(component_type) AS component_type,
        TRIM(title) AS title,
        TRIM(content) AS content
    FROM RAW.KNOWLEDGE_DOC
    WHERE doc_id IS NOT NULL AND TRIM(doc_id) <> ''
) s
ON t.doc_id = s.doc_id
WHEN MATCHED THEN UPDATE SET
    t.doc_type = s.doc_type,
    t.machine_type = s.machine_type,
    t.component_type = s.component_type,
    t.title = s.title,
    t.content = s.content,
    t._loaded_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    doc_id, doc_type, machine_type, component_type, title, content
) VALUES (
    s.doc_id, s.doc_type, s.machine_type, s.component_type, s.title, s.content
);

-- 18. Transform SENSOR_READING_HOURLY
MERGE INTO CORE.SENSOR_READING_HOURLY t
USING (
    SELECT DISTINCT
        TRIM(sensor_id) AS sensor_id,
        TRY_TO_TIMESTAMP_NTZ(ts) AS ts,
        TRY_TO_DOUBLE(run_fraction) AS run_fraction,
        TRY_TO_DOUBLE(avg_running) AS avg_running,
        TRY_TO_DOUBLE(min_running) AS min_running,
        TRY_TO_DOUBLE(max_running) AS max_running
    FROM RAW.SENSOR_READING_HOURLY
    WHERE sensor_id IS NOT NULL AND ts IS NOT NULL
) s
ON t.sensor_id = s.sensor_id AND t.ts = s.ts
WHEN MATCHED THEN UPDATE SET
    t.run_fraction = s.run_fraction,
    t.avg_running = s.avg_running,
    t.min_running = s.min_running,
    t.max_running = s.max_running,
    t._loaded_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    sensor_id, ts, run_fraction, avg_running, min_running, max_running
) VALUES (
    s.sensor_id, s.ts, s.run_fraction, s.avg_running, s.min_running, s.max_running
);

-- 19. Transform SENSOR_READING (High Frequency Telemetry) - Atomic Transient Swap
CREATE OR REPLACE TRANSIENT TABLE CORE.SENSOR_READING_STAGE LIKE CORE.SENSOR_READING;

INSERT INTO CORE.SENSOR_READING_STAGE (sensor_id, ts, value)
SELECT
    TRIM(sensor_id) AS sensor_id,
    TRY_TO_TIMESTAMP_NTZ(ts) AS ts,
    TRY_TO_DOUBLE(value) AS value
FROM RAW.SENSOR_READING
WHERE sensor_id IS NOT NULL AND ts IS NOT NULL AND value IS NOT NULL
  AND _batch_id = (SELECT MAX(_batch_id) FROM RAW.SENSOR_READING);

ALTER TABLE CORE.SENSOR_READING SWAP WITH CORE.SENSOR_READING_STAGE;

DROP TABLE IF EXISTS CORE.SENSOR_READING_STAGE;
