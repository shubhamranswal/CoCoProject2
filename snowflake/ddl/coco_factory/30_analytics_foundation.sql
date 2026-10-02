-- 30_analytics_foundation.sql
-- Milestone 2 Analytics Foundation: Machine Health, OEE, Downtime, Maintenance, Inventory Risk, Production Context
-- Canonical application-facing schema strictly aligned with domain models and SnowflakeRepository

USE DATABASE COCO_FACTORY;
USE SCHEMA ANALYTICS;

-- 1. Machine Health Daily View (Phase 2A.1)
CREATE OR REPLACE VIEW MACHINE_HEALTH_DAILY AS
WITH telemetry_daily AS (
    SELECT
        s.machine_id,
        DATE(h.ts) AS metric_date,
        COUNT(*) AS reading_count,
        ROUND(AVG(CASE WHEN s.sensor_type IN ('vibration_rms', 'vibration', 'VIBRATION') THEN h.avg_running END), 4) AS avg_vibration,
        ROUND(MAX(CASE WHEN s.sensor_type IN ('vibration_rms', 'vibration', 'VIBRATION') THEN h.max_running END), 4) AS max_vibration,
        ROUND(AVG(CASE WHEN s.sensor_type IN ('bearing_temperature', 'winding_temperature', 'temperature', 'TEMPERATURE') THEN h.avg_running END), 4) AS avg_temperature,
        ROUND(MAX(CASE WHEN s.sensor_type IN ('bearing_temperature', 'winding_temperature', 'temperature', 'TEMPERATURE') THEN h.max_running END), 4) AS max_temperature,
        SUM(CASE
            WHEN s.threshold_direction = 'above' AND (h.max_running > s.warn_threshold OR h.max_running > s.crit_threshold) THEN 1
            WHEN s.threshold_direction = 'below' AND (h.min_running < s.warn_threshold OR h.min_running < s.crit_threshold) THEN 1
            ELSE 0
        END) AS exceedance_count
    FROM COCO_FACTORY.CORE.SENSOR_READING_HOURLY h
    JOIN COCO_FACTORY.CORE.SENSOR s ON h.sensor_id = s.sensor_id
    GROUP BY s.machine_id, DATE(h.ts)
),
downtime_daily AS (
    SELECT
        machine_id,
        DATE(start_ts) AS metric_date,
        SUM(duration_min) AS downtime_minutes,
        COUNT(CASE WHEN category = 'breakdown' THEN 1 END) AS breakdown_count
    FROM COCO_FACTORY.CORE.DOWNTIME_EVENT
    GROUP BY machine_id, DATE(start_ts)
),
maintenance_daily AS (
    SELECT
        machine_id,
        COALESCE(scheduled_date, DATE(opened_ts)) AS metric_date,
        COUNT(DISTINCT wo_id) AS maintenance_count
    FROM COCO_FACTORY.CORE.MAINTENANCE_WORK_ORDER
    GROUP BY machine_id, COALESCE(scheduled_date, DATE(opened_ts))
),
alerts_daily AS (
    SELECT
        machine_id,
        DATE(ts) AS metric_date,
        COUNT(*) AS open_alerts,
        COUNT(CASE WHEN UPPER(severity) = 'CRITICAL' THEN 1 END) AS critical_alert_count
    FROM COCO_FACTORY.CORE.ALERT
    GROUP BY machine_id, DATE(ts)
),
predictions_latest AS (
    SELECT
        machine_id,
        DATE(scored_ts) AS metric_date,
        prediction_id AS latest_prediction_id,
        failure_prob AS latest_failure_prob,
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
        m.line_id AS line_name,
        m.criticality,
        t.metric_date
    FROM COCO_FACTORY.CORE.MACHINE m
    CROSS JOIN (
        SELECT DISTINCT DATE(ts) AS metric_date FROM COCO_FACTORY.CORE.SENSOR_READING_HOURLY
    ) t
)
SELECT
    cm.machine_id,
    cm.metric_date,
    cm.machine_name,
    cm.machine_type,
    cm.line_id,
    cm.line_name,
    COALESCE(td.reading_count, 0) AS reading_count,
    td.avg_vibration,
    td.max_vibration,
    td.avg_temperature,
    td.max_temperature,
    COALESCE(td.exceedance_count, 0) AS exceedance_count,
    COALESCE(dd.downtime_minutes, 0.0) AS downtime_minutes,
    COALESCE(dd.breakdown_count, 0) AS breakdown_count,
    COALESCE(md.maintenance_count, 0) AS maintenance_count,
    COALESCE(ad.open_alerts, 0) AS open_alerts,
    p.latest_prediction_id,
    p.latest_failure_prob,
    COALESCE(p.latest_risk_level, 'low') AS latest_risk_level,
    CASE
        WHEN COALESCE(p.latest_failure_prob, 0.0) >= 0.85 OR COALESCE(ad.critical_alert_count, 0) > 0 OR COALESCE(dd.breakdown_count, 0) > 0 THEN 'CRITICAL'
        WHEN COALESCE(p.latest_failure_prob, 0.0) >= 0.60 OR COALESCE(ad.open_alerts, 0) > 0 OR COALESCE(td.exceedance_count, 0) > 0 THEN 'WARNING'
        ELSE 'HEALTHY'
    END AS health_status
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
    pr.shift_date AS metric_date,
    m.machine_name,
    m.line_id,
    SUM(pr.planned_time_min) AS planned_production_minutes,
    SUM(pr.run_time_min) AS operating_minutes,
    SUM(pr.unplanned_downtime_min) AS unplanned_downtime_minutes,
    SUM(pr.total_count) AS total_pieces,
    SUM(pr.good_count) AS good_pieces,
    SUM(pr.reject_count) AS reject_pieces,
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
GROUP BY pr.machine_id, pr.shift_date, m.machine_name, m.line_id;

-- 3. Downtime Analytics Daily View (Phase 2A.3)
CREATE OR REPLACE VIEW DOWNTIME_DAILY AS
WITH downtime_aggregated AS (
    SELECT
        d.machine_id,
        m.machine_name,
        m.line_id,
        DATE(d.start_ts) AS metric_date,
        COUNT(DISTINCT d.event_id) AS total_event_count,
        COUNT(CASE WHEN d.category = 'breakdown' THEN 1 END) AS breakdown_event_count,
        ROUND(SUM(d.duration_min), 2) AS total_downtime_minutes,
        ROUND(SUM(CASE WHEN d.category = 'breakdown' THEN d.duration_min ELSE 0 END), 2) AS breakdown_minutes,
        ROUND(SUM(CASE WHEN d.category = 'changeover' THEN d.duration_min ELSE 0 END), 2) AS changeover_minutes,
        ROUND(SUM(CASE WHEN d.category = 'minor_stop' THEN d.duration_min ELSE 0 END), 2) AS minor_stop_minutes,
        ROUND(SUM(CASE WHEN d.category = 'no_material' THEN d.duration_min ELSE 0 END), 2) AS no_material_minutes,
        ROUND(SUM(CASE WHEN d.category = 'no_operator' THEN d.duration_min ELSE 0 END), 2) AS no_operator_minutes,
        ROUND(SUM(CASE WHEN d.category = 'planned_maintenance' THEN d.duration_min ELSE 0 END), 2) AS planned_maintenance_minutes
    FROM COCO_FACTORY.CORE.DOWNTIME_EVENT d
    JOIN COCO_FACTORY.CORE.MACHINE m ON d.machine_id = m.machine_id
    GROUP BY d.machine_id, m.machine_name, m.line_id, DATE(d.start_ts)
),
top_cause AS (
    SELECT
        machine_id,
        DATE(start_ts) AS metric_date,
        reason_code AS top_reason_code,
        category AS top_downtime_category,
        ROW_NUMBER() OVER (PARTITION BY machine_id, DATE(start_ts) ORDER BY duration_min DESC) AS rn
    FROM COCO_FACTORY.CORE.DOWNTIME_EVENT
)
SELECT
    da.machine_id,
    da.metric_date,
    da.machine_name,
    da.line_id,
    da.total_downtime_minutes,
    da.breakdown_minutes,
    da.changeover_minutes,
    da.minor_stop_minutes,
    da.no_material_minutes,
    da.no_operator_minutes,
    da.planned_maintenance_minutes,
    da.breakdown_event_count,
    da.total_event_count,
    tc.top_reason_code,
    tc.top_downtime_category
FROM downtime_aggregated da
LEFT JOIN top_cause tc ON da.machine_id = tc.machine_id AND da.metric_date = tc.metric_date AND tc.rn = 1;

-- 4. Maintenance Analytics Daily View (Phase 2A.4)
CREATE OR REPLACE VIEW MAINTENANCE_DAILY AS
SELECT
    w.machine_id,
    COALESCE(w.scheduled_date, DATE(w.opened_ts)) AS metric_date,
    m.machine_name,
    m.line_id,
    COUNT(DISTINCT w.wo_id) AS work_order_count,
    COUNT(CASE WHEN w.wo_type = 'corrective' THEN 1 END) AS corrective_count,
    COUNT(CASE WHEN w.wo_type = 'preventive' THEN 1 END) AS preventive_count,
    COUNT(CASE WHEN w.source = 'breakdown' THEN 1 END) AS breakdown_count,
    ROUND(SUM(COALESCE(w.labor_hours, 0)), 2) AS total_labor_hours,
    ROUND(SUM(COALESCE(w.parts_cost, 0)), 2) AS total_parts_cost_inr,
    ROUND(SUM(COALESCE(w.labor_cost, 0)), 2) AS total_labor_cost_inr,
    ROUND(SUM(COALESCE(w.cost, 0)), 2) AS total_maintenance_cost_inr,
    ROUND(AVG(CASE WHEN w.status = 'closed' AND w.labor_hours > 0 THEN w.labor_hours * 60.0 END), 2) AS mean_time_to_repair_minutes
FROM COCO_FACTORY.CORE.MAINTENANCE_WORK_ORDER w
JOIN COCO_FACTORY.CORE.MACHINE m ON w.machine_id = m.machine_id
GROUP BY w.machine_id, COALESCE(w.scheduled_date, DATE(w.opened_ts)), m.machine_name, m.line_id;

-- 5. Inventory Risk View (Phase 2A.5)
CREATE OR REPLACE VIEW INVENTORY_RISK AS
WITH open_po AS (
    SELECT
        part_id,
        COUNT(DISTINCT po_id) AS open_po_count,
        SUM(qty) AS open_po_qty,
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
    sp.supplier_id,
    s.supplier_name,
    COALESCE(po.open_po_count, 0) AS open_po_count,
    COALESCE(po.open_po_qty, 0) AS open_po_qty,
    CASE
        WHEN sp.stock_qty = 0 THEN 'STOCKOUT'
        WHEN sp.stock_qty <= sp.reorder_level THEN 'LOW_STOCK'
        ELSE 'HEALTHY'
    END AS stock_status,
    CASE
        WHEN sp.stock_qty = 0 AND (COALESCE(par.max_failure_prob, 0.0) >= 0.70 OR COALESCE(par.has_critical_machine_dependency, FALSE)) THEN TRUE
        ELSE FALSE
    END AS is_critical_exposure
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
    po.product_id,
    p.product_name,
    po.customer,
    po.priority,
    po.status,
    po.planned_qty,
    po.produced_qty,
    ROUND(
        CASE WHEN po.planned_qty > 0
             THEN LEAST(100.0, (CAST(po.produced_qty AS FLOAT) / po.planned_qty) * 100.0)
             ELSE 0.0 END, 2
    ) AS progress_pct,
    po.due_date,
    GREATEST(0, DATEDIFF(day, CURRENT_DATE(), po.due_date)) AS days_until_due,
    CASE
        WHEN po.due_date < CURRENT_DATE() AND po.status NOT IN ('completed', 'closed') THEN TRUE
        ELSE FALSE
    END AS is_overdue,
    p.unit_price_inr,
    ROUND(po.planned_qty * p.unit_price_inr, 2) AS order_value_inr,
    ROUND(GREATEST(0, po.planned_qty - po.produced_qty) * p.unit_price_inr, 2) AS unfulfilled_revenue_exposure_inr
FROM COCO_FACTORY.CORE.PRODUCTION_ORDER po
JOIN COCO_FACTORY.CORE.MACHINE m ON po.machine_id = m.machine_id
JOIN COCO_FACTORY.CORE.PRODUCT p ON po.product_id = p.product_id;
