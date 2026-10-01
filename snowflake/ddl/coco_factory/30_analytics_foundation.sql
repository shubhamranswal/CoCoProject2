-- 30_analytics_foundation.sql
-- Milestone 2 Analytics Foundation: Machine Health, OEE, Downtime, Maintenance, Inventory Risk, Production Context

USE DATABASE COCO_FACTORY;
USE SCHEMA ANALYTICS;

-- 1. Machine Health Daily View (Phase 2A.1)
CREATE OR REPLACE VIEW MACHINE_HEALTH_DAILY AS
WITH telemetry_daily AS (
    SELECT
        s.machine_id,
        DATE(h.ts) AS metric_date,
        COUNT(*) AS reading_count,
        ROUND(AVG(h.avg_running), 4) AS avg_sensor_value,
        ROUND(MAX(h.max_running), 4) AS max_sensor_value,
        ROUND(AVG(CASE WHEN s.sensor_type IN ('vibration_rms', 'vibration', 'VIBRATION') THEN h.avg_running END), 4) AS vibration_mean,
        ROUND(MAX(CASE WHEN s.sensor_type IN ('vibration_rms', 'vibration', 'VIBRATION') THEN h.max_running END), 4) AS vibration_max,
        ROUND(AVG(CASE WHEN s.sensor_type IN ('bearing_temperature', 'winding_temperature', 'temperature', 'TEMPERATURE') THEN h.avg_running END), 4) AS temperature_mean,
        ROUND(MAX(CASE WHEN s.sensor_type IN ('bearing_temperature', 'winding_temperature', 'temperature', 'TEMPERATURE') THEN h.max_running END), 4) AS temperature_max,
        SUM(CASE
            WHEN s.threshold_direction = 'above' AND h.max_running > s.warn_threshold THEN 1
            WHEN s.threshold_direction = 'below' AND h.min_running < s.warn_threshold THEN 1
            ELSE 0
        END) AS warn_threshold_exceedance_count,
        SUM(CASE
            WHEN s.threshold_direction = 'above' AND h.max_running > s.crit_threshold THEN 1
            WHEN s.threshold_direction = 'below' AND h.min_running < s.crit_threshold THEN 1
            ELSE 0
        END) AS crit_threshold_exceedance_count
    FROM COCO_FACTORY.CORE.SENSOR_READING_HOURLY h
    JOIN COCO_FACTORY.CORE.SENSOR s ON h.sensor_id = s.sensor_id
    GROUP BY s.machine_id, DATE(h.ts)
),
downtime_daily AS (
    SELECT
        machine_id,
        DATE(start_ts) AS metric_date,
        SUM(duration_min) AS downtime_minutes,
        COUNT(DISTINCT event_id) AS downtime_event_count
    FROM COCO_FACTORY.CORE.DOWNTIME_EVENT
    GROUP BY machine_id, DATE(start_ts)
),
maintenance_daily AS (
    SELECT
        machine_id,
        COALESCE(scheduled_date, DATE(opened_ts)) AS metric_date,
        COUNT(DISTINCT wo_id) AS maintenance_event_count
    FROM COCO_FACTORY.CORE.MAINTENANCE_WORK_ORDER
    GROUP BY machine_id, COALESCE(scheduled_date, DATE(opened_ts))
),
alerts_daily AS (
    SELECT
        machine_id,
        DATE(ts) AS metric_date,
        COUNT(*) AS alert_count,
        COUNT(CASE WHEN severity = 'CRITICAL' THEN 1 END) AS critical_alert_count
    FROM COCO_FACTORY.CORE.ALERT
    GROUP BY machine_id, DATE(ts)
),
predictions_latest AS (
    SELECT
        machine_id,
        DATE(scored_ts) AS metric_date,
        failure_prob AS latest_prediction_prob,
        risk_level AS latest_risk_level,
        ROW_NUMBER() OVER (PARTITION BY machine_id, DATE(scored_ts) ORDER BY scored_ts DESC) AS rn
    FROM COCO_FACTORY.CORE.PREDICTION
),
calendar_machines AS (
    SELECT DISTINCT
        m.machine_id,
        m.machine_name,
        m.machine_type,
        m.plant_id,
        m.line_id,
        m.criticality,
        t.metric_date
    FROM COCO_FACTORY.CORE.MACHINE m
    CROSS JOIN (
        SELECT DISTINCT DATE(ts) AS metric_date FROM COCO_FACTORY.CORE.SENSOR_READING_HOURLY
    ) t
)
SELECT
    cm.metric_date,
    cm.machine_id,
    cm.machine_name,
    cm.machine_type,
    cm.plant_id,
    cm.line_id,
    cm.criticality,
    COALESCE(td.reading_count, 0) AS reading_count,
    td.vibration_mean,
    td.vibration_max,
    td.temperature_mean,
    td.temperature_max,
    td.avg_sensor_value,
    td.max_sensor_value,
    COALESCE(td.warn_threshold_exceedance_count, 0) AS warn_threshold_exceedance_count,
    COALESCE(td.crit_threshold_exceedance_count, 0) AS crit_threshold_exceedance_count,
    COALESCE(dd.downtime_minutes, 0.0) AS downtime_minutes,
    COALESCE(md.maintenance_event_count, 0) AS maintenance_event_count,
    COALESCE(ad.alert_count, 0) AS alert_count,
    COALESCE(ad.critical_alert_count, 0) AS critical_alert_count,
    COALESCE(p.latest_prediction_prob, 0.0) AS latest_prediction_prob,
    COALESCE(p.latest_risk_level, 'low') AS latest_risk_level,
    CASE
        WHEN COALESCE(p.latest_prediction_prob, 0.0) >= 0.85 OR COALESCE(ad.critical_alert_count, 0) > 0 OR COALESCE(td.crit_threshold_exceedance_count, 0) > 0 THEN 'CRITICAL'
        WHEN COALESCE(p.latest_prediction_prob, 0.0) >= 0.60 OR COALESCE(ad.alert_count, 0) > 0 OR COALESCE(td.warn_threshold_exceedance_count, 0) > 0 THEN 'WARNING'
        ELSE 'HEALTHY'
    END AS operational_health_status
FROM calendar_machines cm
LEFT JOIN telemetry_daily td ON cm.machine_id = td.machine_id AND cm.metric_date = td.metric_date
LEFT JOIN downtime_daily dd ON cm.machine_id = dd.machine_id AND cm.metric_date = dd.metric_date
LEFT JOIN maintenance_daily md ON cm.machine_id = md.machine_id AND cm.metric_date = md.metric_date
LEFT JOIN alerts_daily ad ON cm.machine_id = ad.machine_id AND cm.metric_date = ad.metric_date
LEFT JOIN predictions_latest p ON cm.machine_id = p.machine_id AND cm.metric_date = p.metric_date AND p.rn = 1;

-- 2. Machine OEE Daily View (Phase 2A.2)
CREATE OR REPLACE VIEW MACHINE_OEE_DAILY AS
SELECT
    pr.machine_id,
    m.machine_name,
    m.line_id,
    pr.shift_date AS metric_date,
    COUNT(DISTINCT pr.run_id) AS total_runs,
    SUM(pr.planned_time_min) AS planned_production_time_min,
    SUM(pr.run_time_min) AS actual_run_time_min,
    SUM(pr.unplanned_downtime_min) AS unplanned_downtime_min,
    SUM(pr.total_count) AS total_production_qty,
    SUM(pr.good_count) AS good_production_qty,
    SUM(pr.reject_count) AS reject_qty,
    AVG(pr.ideal_cycle_time_sec) AS ideal_cycle_time_sec,
    -- Availability: Run Time / Planned Time (bounded [0, 1])
    ROUND(
        CASE WHEN SUM(pr.planned_time_min) > 0
             THEN LEAST(1.0, GREATEST(0.0, SUM(pr.run_time_min) / SUM(pr.planned_time_min)))
             ELSE 1.0 END, 4
    ) AS availability,
    -- Performance: (Total Count * Ideal Cycle Time Sec) / (Run Time Min * 60) (bounded [0, 1])
    ROUND(
        CASE WHEN SUM(pr.run_time_min) > 0
             THEN LEAST(1.0, GREATEST(0.0, (SUM(pr.total_count * pr.ideal_cycle_time_sec) / (SUM(pr.run_time_min) * 60.0))))
             ELSE 1.0 END, 4
    ) AS performance,
    -- Quality: Good Count / Total Count (strictly from canonical counts, bounded [0, 1])
    ROUND(
        CASE WHEN SUM(pr.total_count) > 0
             THEN LEAST(1.0, GREATEST(0.0, CAST(SUM(pr.good_count) AS FLOAT) / SUM(pr.total_count)))
             ELSE 1.0 END, 4
    ) AS quality,
    -- Overall OEE: Availability * Performance * Quality (bounded [0, 1])
    ROUND(
        (CASE WHEN SUM(pr.planned_time_min) > 0 THEN LEAST(1.0, GREATEST(0.0, SUM(pr.run_time_min) / SUM(pr.planned_time_min))) ELSE 1.0 END) *
        (CASE WHEN SUM(pr.run_time_min) > 0 THEN LEAST(1.0, GREATEST(0.0, (SUM(pr.total_count * pr.ideal_cycle_time_sec) / (SUM(pr.run_time_min) * 60.0)))) ELSE 1.0 END) *
        (CASE WHEN SUM(pr.total_count) > 0 THEN LEAST(1.0, GREATEST(0.0, CAST(SUM(pr.good_count) AS FLOAT) / SUM(pr.total_count))) ELSE 1.0 END), 4
    ) AS oee
FROM COCO_FACTORY.CORE.PRODUCTION_RUN pr
JOIN COCO_FACTORY.CORE.MACHINE m ON pr.machine_id = m.machine_id
GROUP BY pr.machine_id, m.machine_name, m.line_id, pr.shift_date;

-- 3. Downtime Analytics Daily View (Phase 2A.3)
CREATE OR REPLACE VIEW DOWNTIME_DAILY AS
WITH downtime_aggregated AS (
    SELECT
        d.machine_id,
        m.machine_name,
        m.line_id,
        DATE(d.start_ts) AS metric_date,
        COUNT(DISTINCT d.event_id) AS downtime_event_count,
        ROUND(SUM(d.duration_min), 2) AS total_downtime_minutes,
        ROUND(SUM(CASE WHEN d.category IN ('planned_maintenance', 'changeover') THEN d.duration_min ELSE 0 END), 2) AS planned_downtime_minutes,
        ROUND(SUM(CASE WHEN d.category NOT IN ('planned_maintenance', 'changeover') THEN d.duration_min ELSE 0 END), 2) AS unplanned_downtime_minutes,
        ROUND(SUM(CASE WHEN d.category = 'breakdown' THEN d.duration_min ELSE 0 END), 2) AS breakdown_downtime_minutes,
        ROUND(SUM(CASE WHEN d.category = 'minor_stop' THEN d.duration_min ELSE 0 END), 2) AS minor_stop_minutes,
        ROUND(SUM(CASE WHEN d.category = 'no_material' THEN d.duration_min ELSE 0 END), 2) AS no_material_minutes,
        ROUND(SUM(CASE WHEN d.category = 'no_operator' THEN d.duration_min ELSE 0 END), 2) AS no_operator_minutes
    FROM COCO_FACTORY.CORE.DOWNTIME_EVENT d
    JOIN COCO_FACTORY.CORE.MACHINE m ON d.machine_id = m.machine_id
    GROUP BY d.machine_id, m.machine_name, m.line_id, DATE(d.start_ts)
),
top_cause AS (
    SELECT
        machine_id,
        DATE(start_ts) AS metric_date,
        reason_code AS top_reason_code,
        category AS top_category,
        ROW_NUMBER() OVER (PARTITION BY machine_id, DATE(start_ts) ORDER BY duration_min DESC) AS rn
    FROM COCO_FACTORY.CORE.DOWNTIME_EVENT
)
SELECT
    da.metric_date,
    da.machine_id,
    da.machine_name,
    da.line_id,
    da.downtime_event_count,
    da.total_downtime_minutes,
    da.planned_downtime_minutes,
    da.unplanned_downtime_minutes,
    da.breakdown_downtime_minutes,
    da.minor_stop_minutes,
    da.no_material_minutes,
    da.no_operator_minutes,
    tc.top_reason_code,
    tc.top_category
FROM downtime_aggregated da
LEFT JOIN top_cause tc ON da.machine_id = tc.machine_id AND da.metric_date = tc.metric_date AND tc.rn = 1;

-- 4. Maintenance Analytics Daily View (Phase 2A.4)
CREATE OR REPLACE VIEW MAINTENANCE_DAILY AS
SELECT
    w.machine_id,
    m.machine_name,
    m.line_id,
    COALESCE(w.scheduled_date, DATE(w.opened_ts)) AS metric_date,
    COUNT(DISTINCT w.wo_id) AS work_order_count,
    COUNT(CASE WHEN w.wo_type = 'corrective' THEN 1 END) AS corrective_work_orders,
    COUNT(CASE WHEN w.wo_type = 'preventive' THEN 1 END) AS preventive_work_orders,
    COUNT(CASE WHEN w.wo_type = 'predictive' THEN 1 END) AS predictive_work_orders,
    COUNT(CASE WHEN w.source = 'breakdown' THEN 1 END) AS breakdown_work_orders,
    COUNT(CASE WHEN w.status = 'closed' THEN 1 END) AS completed_work_orders,
    COUNT(CASE WHEN w.status <> 'closed' THEN 1 END) AS open_work_orders,
    ROUND(SUM(COALESCE(w.labor_hours, 0)), 2) AS maintenance_labor_hours,
    ROUND(SUM(COALESCE(w.parts_cost, 0)), 2) AS parts_cost_inr,
    ROUND(SUM(COALESCE(w.labor_cost, 0)), 2) AS labor_cost_inr,
    ROUND(SUM(COALESCE(w.cost, 0)), 2) AS total_maintenance_cost_inr,
    ROUND(AVG(CASE WHEN w.status = 'closed' AND w.labor_hours > 0 THEN w.labor_hours END), 2) AS mttr_hours
FROM COCO_FACTORY.CORE.MAINTENANCE_WORK_ORDER w
JOIN COCO_FACTORY.CORE.MACHINE m ON w.machine_id = m.machine_id
GROUP BY w.machine_id, m.machine_name, m.line_id, COALESCE(w.scheduled_date, DATE(w.opened_ts));

-- 5. Inventory Risk View (Phase 2A.5)
CREATE OR REPLACE VIEW INVENTORY_RISK AS
WITH open_po AS (
    SELECT
        part_id,
        SUM(qty) AS pending_order_qty,
        MIN(expected_delivery_date) AS earliest_expected_delivery
    FROM COCO_FACTORY.CORE.PURCHASE_ORDER
    WHERE status IN ('pending', 'in_transit', 'ordered', 'PENDING', 'IN_TRANSIT')
    GROUP BY part_id
),
part_asset_risk AS (
    SELECT
        sp.part_id,
        MAX(p.failure_prob) AS max_failure_prob,
        BOOLOR_AGG(m.criticality IN ('A', 'B', 'HIGH', 'CRITICAL')) AS has_critical_machine_dependency
    FROM COCO_FACTORY.CORE.SPARE_PART sp
    JOIN COCO_FACTORY.CORE.COMPONENT c ON sp.compatible_model = c.model OR sp.part_category = c.component_type
    JOIN COCO_FACTORY.CORE.MACHINE m ON c.machine_id = m.machine_id
    LEFT JOIN COCO_FACTORY.CORE.PREDICTION p ON m.machine_id = p.machine_id
    GROUP BY sp.part_id
)
SELECT
    sp.part_id,
    sp.part_name,
    sp.part_category,
    sp.compatible_model,
    sp.stock_qty,
    sp.reorder_level,
    sp.reorder_qty,
    sp.lead_time_days,
    sp.warehouse_bin,
    sp.unit_cost_inr,
    s.supplier_id,
    s.supplier_name,
    s.country AS supplier_country,
    s.on_time_delivery_pct,
    COALESCE(po.pending_order_qty, 0) AS pending_order_qty,
    po.earliest_expected_delivery,
    -- Deterministic stock status
    CASE
        WHEN sp.stock_qty = 0 THEN 'STOCKOUT'
        WHEN sp.stock_qty <= sp.reorder_level THEN 'BELOW_REORDER'
        ELSE 'SUFFICIENT'
    END AS stock_status,
    -- Critical Inventory Exposure: Stockout + High-Criticality Asset or Active Degradation Risk (>= 0.70)
    CASE
        WHEN sp.stock_qty = 0 AND (COALESCE(par.max_failure_prob, 0.0) >= 0.70 OR COALESCE(par.has_critical_machine_dependency, FALSE)) THEN TRUE
        ELSE FALSE
    END AS critical_inventory_exposure
FROM COCO_FACTORY.CORE.SPARE_PART sp
LEFT JOIN COCO_FACTORY.CORE.SUPPLIER s ON sp.supplier_id = s.supplier_id
LEFT JOIN open_po po ON sp.part_id = po.part_id
LEFT JOIN part_asset_risk par ON sp.part_id = par.part_id;

-- 6. Production Context View (Phase 2A.6)
CREATE OR REPLACE VIEW PRODUCTION_CONTEXT AS
SELECT
    po.production_order_id,
    po.machine_id,
    m.machine_name,
    m.line_id,
    m.criticality AS machine_criticality,
    po.product_id,
    p.product_name,
    p.product_family,
    p.unit_price_inr,
    po.customer,
    po.planned_qty,
    po.produced_qty,
    ROUND(
        CASE WHEN po.planned_qty > 0
             THEN LEAST(100.0, (CAST(po.produced_qty AS FLOAT) / po.planned_qty) * 100.0)
             ELSE 0.0 END, 2
    ) AS progress_pct,
    po.planned_start,
    po.planned_end,
    po.due_date,
    po.priority,
    po.status AS order_status,
    CASE
        WHEN po.status IN ('in_progress', 'scheduled', 'ACTIVE', 'IN_PROGRESS') THEN TRUE
        ELSE FALSE
    END AS active_order_flag,
    GREATEST(0, DATEDIFF(day, CURRENT_DATE(), po.due_date)) AS days_until_due,
    ROUND(GREATEST(0, po.planned_qty - po.produced_qty) * p.unit_price_inr, 2) AS remaining_revenue_exposure_inr
FROM COCO_FACTORY.CORE.PRODUCTION_ORDER po
JOIN COCO_FACTORY.CORE.MACHINE m ON po.machine_id = m.machine_id
JOIN COCO_FACTORY.CORE.PRODUCT p ON po.product_id = p.product_id;
